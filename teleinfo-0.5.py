#=============================================================
#   Une premiere tentative de manipulation des trames teleinfo
#
#   Structure generale
#
#   Ce programme cree deux threads pour l'archivage des donnees
#   . Le premier passe son temps a lire des trames sur le port
#   serie et les stocke dans une file de trames horodatees de
#   type Queue.
#   . Le second passe son temps a les consommer dans la Queue
#   et a les transformer en teleinfo puis les envoyer dans la
#   base de donnees. Chaqueteleinfo remplace la precedente dans
#   la variable globale du meme nom. Ainsi les autres threads
#   disposent toujours dans cette variable des informations
#   les plus a jour.
#
#   Principaux "types"
#
#   . Les trames lues par teleinfoReadFrame sont codees comme
#   une simple chaine de caracteres
#   . Les trames horodatees sont stoquees dans la file sous
#   la forme d'un dictionnaire {'trame': trame, 'datetime' :
#   datetime.datetime.now()}
#   . La structure teleinfo utilisee pour stocker les informations
#   d'une trame est un tableau associatif contenant tous les
#   champs de la trame plus un champ DATE et un champ TIME
#   construits a partir de la date de capture de la trame
#   stockee avec elle dans la Queue
#
#-------------------------------------------------------------
#   WARNING : 
#   - A faire
#     . un fichier de log, pour voir l'etat (utiliser la classe
#     logger)
#     . gerer la fin du processus !
#     . une page de config, meme sans edition
#     . un fichier de configuration
#     . les urls dans les pages web
#     . Pourquoi les trames sont parfois erronees ?
#       Apparemment ca viendrait du mode debug de flask
#     . calcul du checksum
#     . s'assurer que ca fontionne meme en cas de panne du
#     serveur de base de donnees
#=============================================================
teleinfoVersion = "0.5"     # Conversion de la page web main
                            # Ajout de useMySQL
                            # Ajout de useThread
#teleinfoVersion = "0.4"    # Utilisation de mySQL
#teleinfoVersion = "0.3"    # Insertion des threads
#teleinfoVersion = "0.2"    # Ajout d'une premiere page web
#teleinfoVersion = "0.1"    # Premiere tentative

#-------------------------------------------------------------

# Pour afficher certains messages de debogage
debug=False

# Si useMySQL est faux, on ne sauvegarde pas sur la BD
useMySQL=True

# Si useThread est faux, on ne lit une nouvelle trame 
# que lors d'une requete. A ne faire que pour debuguer
useThread=True

#-------------------------------------------------------------

from flask import Flask, url_for, render_template, redirect, Response
import json
import sys, time, datetime
import copy
import threading, Queue
import mysql.connector
from mysql.connector import errorcode

#-------------------------------------------------------------

app = Flask(__name__)

devicePath = "/dev/ttyAMA0"
fd=0

#-------------------------------------------------------------
# Le tableau associatif teleinfo contient les informations lues
# dans la derniere trame analysee.
#-------------------------------------------------------------
teleinfo = {}

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
# sous forme d'une trame horodatee.
#   Si le parametre oneShot est faux, alors cette fonction ne
# s'arrete jamais. Elle lit une trame et l'insere dans une
# file d'attente de trames horodatees puis recommence.
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
         if (debug) :
            print "[teleinfoReadFrame] Je renvoie une trame datee : "
            print trame
            print "------------------------------------"
         return {'trame': trame, 'datetime' : datetime.datetime.now()}
      # Sinon on insere dans la file
      else : #WARNING un try catch sur l'insertion
         if (debug) :
            print "[teleinfoReadFrame] J'insere une trame datee : "
            print trame
            print "------------------------------------"

         fileDeTrames.put({'trame': trame, 'datetime' : datetime.datetime.now()})
  
#-------------------------------------------------------------
#   Lecture d'une trame que l'on va transformer en dictionnaire
# dans la variable teleinfo qui est renvoyee.
#   Une estampille temporelle est ajoutee, au format time.time()
# de python, en attendant mieux
#------------------------------------------------------------- 
def parseFrameToTeleinfo(frame) :
   ti = {}
   for line in frame.split('\n') :
      if (len(line) > 0 ) : 
         mots = line.split(' ')
         # WARNING checksum
#         sys.stdout.write("[" + mots[0] + "] = {" + mots[1] + "} - " + mots[2] + "\n")
         ti[mots[0]] =  mots[1]

   return ti

#-------------------------------------------------------------
#   Affichage d'un teleinfo (pour debogage)
#-------------------------------------------------------------
def printDico(ti) :
   print "============="
   for k,v in ti.items():
      print(k)
      print(v)
   print "============="

def printTeleinfo(ti) :
   print "Type de contrat   : " + ti['OPTARIF']
   print "Couleur de demain : " + ti['DEMAIN']
   print "Tarif en cours    : " + ti['PTEC']
   print "Intensite         : " + ti['IINST']
   print "Puissance app     : " + ti['PAPP']
   
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
def insertTeleinfoMySQL(cursor, ti) :
   addTeleinfo =  ("INSERT INTO teleinfo "
                   "(date, time, adco, optarif, isousc, bbrhcjb, bbrhpjb, bbrhcjw, bbrhpjw, bbrhcjr, bbrhpjr, ptec, demain, iinst, imax, papp, hhphc, motdetat) "
                   "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
   dataTeleinfo = (
      ti['DATE'],
      ti['TIME'],
      ti['ADCO'],
      ti['OPTARIF'],
      ti['ISOUSC'],
      ti['BBRHCJB'],
      ti['BBRHPJB'],
      ti['BBRHCJW'],
      ti['BBRHPJW'],
      ti['BBRHCJR'],
      ti['BBRHPJR'],
      ti['PTEC'],
      ti['DEMAIN'],
      ti['IINST'],
      ti['IMAX'],
      ti['PAPP'],
      ti['HHPHC'],
      ti['MOTDETAT']
   )
   cursor.execute(addTeleinfo, dataTeleinfo)

#-------------------------------------------------------------
# Traitement d'une trame horodatee. Elle est transformee en
# une teleinfo. Elle est inseree dans la base de donnees et
# remplace la teleinfo en cours (variable globale)
#-------------------------------------------------------------
def processOneFrame(tr, dbCnx) :
   global teleinfo
   if (debug) :
      print "[processOneFrame] J'ai une trame"

   if (useMySQL) :
      cursor = dbCnx.cursor()

   # on analyse la trame
   ti = parseFrameToTeleinfo(frame = tr['trame'])

   # On la tag avec sa date et heure (WARNING : a faire dans parseFrameToTeleinfo)
   estampille = tr['datetime']
   ti['DATE'] = estampille.date()
   ti['TIME'] = estampille.time()

   # Ca devient la teleinfo "active"
   teleinfoLock.acquire()
   teleinfo = copy.deepcopy(ti)
   teleinfoLock.release()

   # On l'insere dans la BD
   if (useMySQL) :
      if (debug) :
         print "[processOneFrame] Je la mets dans la base"
      insertTeleinfoMySQL(cursor, ti)
      dbCnx.commit()

#-------------------------------------------------------------
# Traitement continu de la file des trames horodatees
#-------------------------------------------------------------
def frameQueueProcess(fileDeTrames, dbCnx) :
   while (True) :
      # On va chercher une {trame, datetime} dans la file
      if (debug) :
         print "[frameQueueProcess] J'attends une trame"
      tr = fileDeTrames.get(True)
      if (debug) :
         print "[frameQueueProcess] J'ai une trame :"
         print tr['trame']
         print "------------------------------------"

      processOneFrame(tr, dbCnx)

#=============================================================
# Gestion de l'interface web
#=============================================================
#-------------------------------------------------------------
# La page principale
#-------------------------------------------------------------
@app.route("/")
def hello():
   # Si on n'utilise pas les threads, forcons une relecture
   if (not useThread) :
      tr = teleinfoReadFrame(fd, True)
      processOneFrame(tr, database)

   teleinfoLock.acquire()
   ti = copy.deepcopy(teleinfo)
   teleinfoLock.release()

   templateData = {
      'version' : teleinfoVersion,
      'BBRHPJB' : ti['BBRHPJB'],
      'BBRHPJW' : ti['BBRHPJW'],
      'BBRHPJR' : ti['BBRHPJR'],
      'BBRHCJB' : ti['BBRHCJB'],
      'BBRHCJW' : ti['BBRHCJW'],
      'BBRHCJR' : ti['BBRHCJR'],
      'ISOUSC' : ti['ISOUSC']
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
   teleinfoLock.acquire()
   ti = copy.deepcopy(teleinfo)
   teleinfoLock.release()

   templateData = {
      'clef' : clef,
      'valeur' : ti[clef]
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
   # Si on n'utilise pas les threads, forcons une relecture
   if (not useThread) :
      tr = teleinfoReadFrame(fd, True)
      processOneFrame(tr, database)
      
   teleinfoLock.acquire()
   ti = copy.deepcopy(teleinfo)
   teleinfoLock.release()

   return Response(json.dumps(int(ti[clef])),mimetype='application/json')

#--------------------------------------------------------
#   Page d'affichage des valeurs instantanees
#--------------------------------------------------------
@app.route("/instantane")
def instantane():
   # Si on n'utilise pas les threads, forcons une relecture
   if (not useThread) :
      tr = teleinfoReadFrame(fd, True)
      processOneFrame(tr, database)
      
   teleinfoLock.acquire()
   ti = copy.deepcopy(teleinfo)
   teleinfoLock.release()
   print "On y va"
   templateData = {
      'version' : teleinfoVersion,
      'BBRHPJB' : ti['BBRHPJB'],
      'BBRHPJW' : ti['BBRHPJW'],
      'BBRHPJR' : ti['BBRHPJR'],
      'BBRHCJB' : ti['BBRHCJB'],
      'BBRHCJW' : ti['BBRHCJW'],
      'BBRHCJR' : ti['BBRHCJR'],
      'ISOUSC' : ti['ISOUSC'],
   }
   return render_template('instantane.html', **templateData)

#=============================================================
#
#=============================================================
print "Teleinfo version " + teleinfoVersion

# Initialisation du port serie
fd=initSerialPort();

# Connexion a la base de donnees
if (useMySQL) :
   database = connectMySQL()
else :
   print "Attention : pas de base de donnees"
   database = {}

# On va inserer les trames dans une file (thread safe !)
# On les inserera dans la base de donnees de facon asynchrone
fileDeTrames = Queue.Queue(100);

# Pour proteger le teleinfo
teleinfoLock = threading.Lock();

# Lancement des threads
if (useThread) :
   threadLecture = threading.Thread(target=teleinfoReadFrame, args=(fd, False,))
   threadSauvegarde = threading.Thread(target=frameQueueProcess, args=(fileDeTrames, database, ))
   threadLecture.start()
   threadSauvegarde.start()
else :
   print "Attention : pas de threads"
   tr = teleinfoReadFrame(fd, True)
   processOneFrame(tr, database)


# On demarre le serveur web
if __name__ == "__main__":
   # Attention, pas de debug en multithreads
   app.run(host='0.0.0.0', port=8081, debug=False)

