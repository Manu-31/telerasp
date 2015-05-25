#=============================================================
#   Une premiere tentative de manipulation des trames teleinfo
#
#   Ce programme cree deux threads pour l'archivage des donnees
#   . Le premier passe son temps a lire des trames sur le port
#   serie et les stocque telles quelles dans une Queue.
#   . Le second passe son temps a les consommer dans la Queue
#   et a les envoyer dans la base de donnees. Chaque structure
#   teleinfo remplace la precedente dans la variable globale
#   du meme nom. Ainsi les autres threads disposent toujours
#   dans cette variable des informations les plus a jour.
#
#   WARNING : 
#   - A faire
#      calcul du checksum
#      gerer la fin du processus !
#   - En cours
#      associer la date a la trame lors de la lecture
#=============================================================
from flask import Flask, url_for, render_template, redirect, Response
import json
import sys, time, datetime
#import random
import threading, Queue
import mysql.connector
from mysql.connector import errorcode

app = Flask(__name__)

devicePath = "/dev/ttyAMA0"
fd=0

#-------------------------------------------------------------
# Le tableau associatif teleinfo contient les informations lues
# dans la derniere trame analysee.
#-------------------------------------------------------------
teleinfo = {}

teleinfoVersion = "0.4"     # Utilisation de mySQL
#teleinfoVersion = "0.3"    # Insertion des threads
#teleinfoVersion = "0.2"    # Ajout d'une premiere page web
#teleinfoVersion = "0.1"    # Premiere tentative

debug=False

#-------------------------------------------------------------
#   Initialisation du port serie
#   Retour : descripteur du port serie ouvert (int)
#-------------------------------------------------------------
def initSerialPort():
   import termios, os

   fd = os.open(devicePath, os.O_RDWR | os.O_NOCTTY)

   # WARNING : gerer les erreurs

   old = termios.tcgetattr(fd)
   new = termios.tcgetattr(fd)

   # c_iflags
   new[0] = new[0] | (termios.INPCK | termios.ISTRIP)
   new[0] = new[0] & ~(termios.IXON | termios.IXOFF | termios.IXANY | termios.ICRNL)

   # c_oflags
   new[1] = new[1] & ~termios.OPOST

   # c_cflags
   new[2] = new[2] &  ~termios.CSIZE
   new[2] = new[2] | termios.CLOCAL | termios.CREAD | termios.PARENB | termios.CS7
   new[2] = new[2] &  ~termios.PARODD
   new[2] = new[2] &  ~termios.CSTOPB
   new[2] = new[2] &  ~termios.CRTSCTS

   # c_lfags
   new[3] = new[3] & ~(termios.ECHO | termios.ICANON | termios.ECHOE | termios.ISIG)

   # ispeed
   new[4] = termios.B1200

   # ospeed
   new[5] = termios.B1200

   # cc
   new[6][termios.VMIN] = 0
   new[6][termios.VTIME] = 80

   # flush
   termios.tcflush(fd, termios.TCIOFLUSH)

   #on applique
   termios.tcsetattr(fd, termios.TCSANOW, new)

   return fd

#-------------------------------------------------------------
#   Lecture de trames depuis l'interface serie. Si le parametre
# oneShot est True, on ne lit qu'une trame, elle est retournee
# sous forme d'une chaine de caracteres.
#   Si le parametre oneShot est faux, alors cette fonction ne
# s'arrete jamais. Elle lit une trame et l'insere dans une
# file d'attente puis recommence.
#-------------------------------------------------------------
def teleinfoReadFrame(fd, oneShot=True):
   import os
   c = "x"
#   print("Lecture d'une trame dans fd " + str(fd) + "\n");

   # On lit sans s'arreter (il y aura un return si oneShot)
   while (True) :
      cp = c
      c = os.read(fd, 1)
#      sys.stdout.write(hex(ord(c)) + " ")
#      n = 0

#      print("On attend la fin de la trame en cours\n")
      while (not((ord(c) == 0x02) and (ord(cp) == 0x03))) :
         cp = c
         c = os.read(fd, 1)
#         sys.stdout.write(hex(ord(c)) + " ")
#         if (n == 7):
#            sys.stdout.write("\n")
#            n = 0
#         else :
#            n = n + 1 
#   print("On passe a la suite\n")
      cp = c
      c = os.read(fd, 1)
      trame = ""
      while (not(ord(c) == 0x03)) :
         trame = trame + c
         cp = c
         c = os.read(fd, 1)

      # Si on en voulait qu'une, on la renvoie
      if (oneShot) :
         return trame
      # Sinon on insere dans la file
      else : #WARNING un try catch sur l'insertion
         print "[teleinfoReadFrame] J'insere une trame datee"
         fileDeTrames.put({'trame': trame, 'datetime' : datetime.datetime.now()})
  
#-------------------------------------------------------------
#   Lecture d'une trame que l'on va transformer en dictionnaire
# dans la variable teleinfo qui est renvoyee.
#   Une estampille temporelle est ajoutee, au format time.time()
# de python, en attendant mieux
#------------------------------------------------------------- 
def parseFrameToTeleinfo(frame) :
   teleinfo = { # WARNING a virer
      'DATIME' : datetime.datetime.now()
   }
   for line in frame.split('\n') :
      if (len(line) > 0 ) : 
         mots = line.split(' ')
         # WARNING checksum
#         sys.stdout.write("[" + mots[0] + "] = {" + mots[1] + "} - " + mots[2] + "\n")
         teleinfo[mots[0]] =  mots[1]

   return teleinfo

#-------------------------------------------------------------
#   Affichage d'un teleinfo (pour debogage)
#-------------------------------------------------------------
def printTeleinfo(teleinfo) :
   print "Type de contrat   : " + teleinfo['OPTARIF']
   print "Couleur de demain : " + teleinfo['DEMAIN']
   print "Tarif en cours    : " + teleinfo['PTEC']
   print "Intensite         : " + teleinfo['IINST']
   print "Puissance app     : " + teleinfo['PAPP']
   
#=============================================================
#   Gestion de la base de donnees
#=============================================================

#-------------------------------------------------------------
# Connexion a la base mySQL
#-------------------------------------------------------------
def connectMySQL() :
   try:
      connexion = mysql.connector.connect(
         host='mani.manu-chaput.net',
         user='teleinfo',
         password='chaput',
         database='Domotique')

   except mysql.connector.Error as err:
      if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
        print "Erreur d'authentification"
      elif err.errno == errorcode.ER_BAD_DB_ERROR:
         print "Base inconnue"
      else:
         print "Erreur d'acces a la base"
         print(err)
      return
   else:
      if (debug) :
         print "Connecte a la base"

   return connexion

#-------------------------------------------------------------
# Insertion d'un jeu de mesure dans la base mySQL
#-------------------------------------------------------------
def insertTeleinfoMySQL(cursor, teleinfo) :
   addTeleinfo =  ("INSERT INTO teleinfo "
                   "(date, time, adco, optarif, isousc, bbrhcjb, bbrhpjb, bbrhcjw, bbrhpjw, bbrhcjr, bbrhpjr, ptec, demain, iinst, imax, papp, hhphc, motdetat) "
                   "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
   dataTeleinfo = (
      teleinfo['DATE'],
      teleinfo['TIME'],
      teleinfo['ADCO'],
      teleinfo['OPTARIF'],
      teleinfo['ISOUSC'],
      teleinfo['BBRHCJB'],
      teleinfo['BBRHPJB'],
      teleinfo['BBRHCJW'],
      teleinfo['BBRHPJW'],
      teleinfo['BBRHCJR'],
      teleinfo['BBRHPJR'],
      teleinfo['PTEC'],
      teleinfo['DEMAIN'],
      teleinfo['IINST'],
      teleinfo['IMAX'],
      teleinfo['PAPP'],
      teleinfo['HHPHC'],
      teleinfo['MOTDETAT']
   )
   cursor.execute(addTeleinfo, dataTeleinfo)

#-------------------------------------------------------------
# Traitement continu de la file des trames
#-------------------------------------------------------------
def frameQueueProcess(fileDeTrames, dbCnx) :
   cursor = dbCnx.cursor()
   while (True) :
      # On va chercher une {trame, datetime} dans la file
      if (debug) :
         print "[frameQueueProcess] J'attends une trame"
      tr = fileDeTrames.get(True)
      if (debug) :
         print "[frameQueueProcess] J'ai une trame"

      # on analyse la trame
      # WARNING mutexlock
      teleinfo = parseFrameToTeleinfo(frame = tr['trame'])

      # On la tag avec sa date et heure (WARNING : a faire dans parseFrameToTeleinfo)
      estampille = tr['datetime']
      teleinfo['DATE'] = estampille.date()
      teleinfo['TIME'] = estampille.time()
      # WARNING mutexunlock
      if (debug) :
         print "[frameQueueProcess] Je la mets dans la base"

      # On l'insere dans la BD
      insertTeleinfoMySQL(cursor, teleinfo)
      dbCnx.commit()

#=============================================================
# Gestion de l'interface web
#=============================================================
#-------------------------------------------------------------
# La page principale
#-------------------------------------------------------------
@app.route("/")
def hello():
   templateData = {
      'version' : teleinfoVersion,
      'BBRHPJB' : teleinfo['BBRHPJB'],
      'BBRHPJW' : teleinfo['BBRHPJW'],
      'BBRHPJR' : teleinfo['BBRHPJR'],
      'BBRHCJB' : teleinfo['BBRHCJB'],
      'BBRHCJW' : teleinfo['BBRHCJW'],
      'BBRHCJR' : teleinfo['BBRHCJR'],
      'ISOUSC' : teleinfo['ISOUSC'],
   }
   return render_template('main.html', **templateData)

#--------------------------------------------------------
# La route suivante permet d'acceder a toutes les valeurs
# de la derniere trame lue. clef est le nom du label de
# la trame. La page fournie contient simplement la valeur
# sans fioriture
#--------------------------------------------------------
@app.route("/teleinfo/<clef>")
def lireClef(clef):
   templateData = {
      'clef' : clef,
      'valeur' : teleinfo[clef]
   }
   return render_template('clef.html', **templateData)
 
#--------------------------------------------------------
# La route suivante permet d'acceder a toutes les valeurs
# de la derniere trame lue. clef est le nom du label de
# la trame. La page fournie contient simplement la valeur
# mis en forme par JSON
#--------------------------------------------------------
@app.route("/json/<clef>")
def lireClefJSON(clef):
   templateData = {
      'clef' : clef,
      'valeur' : teleinfo[clef]
   }
   return Response(json.dumps(int(teleinfo[clef])),mimetype='application/json')

#--------------------------------------------------------
# La fonction suivante fournit un point pour la courbe
# de puissance. La page fournie contient simplement la valeur
# mis en forme par JSON.
# WARNING : pour le moment, on calcule a la volee, mais
# des que la BD est en place, on passera par la.
#--------------------------------------------------------
@app.route("/json/puissance/<clef>")
def puissance(clef):
   global teleinfo

   # On sauve l'ancienne valeur + date
   valeur = int(teleinfo[clef])
   avant = teleinfo['DATIME']

   # On fait une nouvelle lecture
   print "On en lit une autre" 
   teleinfo = parseFrameToTeleinfo(teleinfoReadFrame(fd, True))  

   # Ce qui a ete consomme sur la duree
   valeur = int(teleinfo[clef]) - valeur

   # La duree
   duree = datetime.timedelta.total_seconds(teleinfo['DATIME'] - avant)

   print "Conso " + str(valeur) + " en " + str(duree) + " secondes"

   puissance = valeur / duree

   now = datetime.datetime.now()
   x = datetime.timedelta.total_seconds(now-datetime.datetime(1970, 1, 1))

   print "[x=" + str(x) + ", " + str(puissance) + "]"

   coord = [ x, puissance ]

   return Response(json.dumps(coord),mimetype='application/json')

@app.route("/instantane")
def instantane():
   templateData = {
      'version' : "0.2",
      'BBRHPJB' : teleinfo['BBRHPJB'],
      'BBRHPJW' : teleinfo['BBRHPJW'],
      'BBRHPJR' : teleinfo['BBRHPJR'],
      'BBRHCJB' : teleinfo['BBRHCJB'],
      'BBRHCJW' : teleinfo['BBRHCJW'],
      'BBRHCJR' : teleinfo['BBRHCJR'],
      'ISOUSC' : teleinfo['ISOUSC'],
   }
   return render_template('instantane.html', **templateData)

#=============================================================
#
#=============================================================
print "Teleinfo version " + teleinfoVersion

# Initialisation du port serie
fd=initSerialPort();

# Connexion a la base de donnees
database = connectMySQL()

# On va inserer les trames dans une file (thread safe !)
# On les inserera dans la base de donnees de facon asynchrone
fileDeTrames = Queue.Queue(100);

# Lancement des threads
threadLecture = threading.Thread(target=teleinfoReadFrame, args=(fd, False,))
threadSauvegarde = threading.Thread(target=frameQueueProcess, args=(fileDeTrames, database, ))

threadLecture.start()
threadSauvegarde.start()

# On demarre le serveur web
if __name__ == "__main__":
   app.run(host='0.0.0.0', port=8081, debug=False)

