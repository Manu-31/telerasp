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
#     . Passer les clefs des teleinfo en minuscule
#     . Un cache des donnees des pages !
#     . diffents modes de debug configures par le fichier
#     . une page de config, meme sans edition
#     . un fichier de configuration (qui permettra un comportement
#     different pour root !) avec ConfigParser
#     . les urls dans les pages web
#     . Pourquoi les trames sont parfois erronees ?
#       Apparemment ca viendrait du mode debug de flask
#     . s'assurer que ca fonctionne meme en cas de panne du
#     serveur de base de donnees
#     . gerer les erreurs internes, avec un try catch sur les
#     pages web en traitant l'exception KeyError par exemple
#   FAIT
#     . calcul du checksum
#     . gerer la fin du processus !
#     . un fichier de log, pour voir l'etat (utiliser la classe
#     logger)
#=============================================================
teleinfoVersion  = "0.9"    # Premiere vraie page depuis la BD
                            # Ajout de l'option -l
                            # Ajout de la verification des trames
                            # Introductin dun debug thematique
#teleinfoVersion = "0.8"    # Ajout de parametres
                            # on peut maintenant laisser tourner
                            # le remplissage de la base et
                            # faire evoluer la partie web
#teleinfoVersion = "0.7"    # Utilisation de la base en lecture
#teleinfoVersion = "0.6"    # Insertion du logger
#teleinfoVersion = "0.5"    # Conversion de la page web main
                            # Ajout de useMySQL
                            # Ajout de useThread
#teleinfoVersion = "0.4"    # Utilisation de mySQL
#teleinfoVersion = "0.3"    # Insertion des threads
#teleinfoVersion = "0.2"    # Ajout d'une premiere page web
#teleinfoVersion = "0.1"    # Premiere tentative

#-------------------------------------------------------------

#=============================================================
#   Configuration
#=============================================================

#-------------------------------------------------------------
# La configuration generale
#-------------------------------------------------------------
# Pour afficher certains messages de debogage
debug={
#   'serial',   # Sur le port serie
#   'frames',   # La gestion des trames
   'web',      # L'affichage de pages
#   'mysql'     # L'acces a la BD
}

# Si useMySQL est faux, on ne sauvegarde pas sur la BD
useMySQL=True

# Si useThread est faux, on ne lit une nouvelle trame 
# que lors d'une requete. A ne faire que pour debuguer
useThread=True

# Faut-il lancer le serveur Web ?
runWebServer = True

# Peut-on faire des lectures de trame ?
# La valeur False n'a d'interet que pour le debogage pour le
# moment. Il pourra servir a faire un serveur web qui ne lit
# pas de valeur instantanee, pendant qu'un autre processus ne 
# fera que de la lecture sans service web.
readFrames=True

#-------------------------------------------------------------
# Le contrat EDF  
#-------------------------------------------------------------
tarifHPJB = 1.0

# Liste des etiquettes presentes dans une trame en fonction du
# contrat. Une trame qui ne contient pas toutes ces etiquettes
# et uniquement celles la sera rejetee.
clefsContrat = {
   'ADCO',
   'OPTARIF',
   'ISOUSC',
   'BBRHCJB',
   'BBRHPJB',
   'BBRHCJW',
   'BBRHPJW',
   'BBRHCJR',
   'BBRHPJR',
   'PTEC',
   'DEMAIN',
   'IINST',
   'IMAX',
   'PAPP',
   'HHPHC',
   'MOTDETAT'
}

#-------------------------------------------------------------
# La source de donnees
#-------------------------------------------------------------
# Le device du port serie
devicePath = "/dev/ttyAMA0"

#-------------------------------------------------------------
# La base de donnees
#-------------------------------------------------------------
# Le serveur mySQL
mySQLServer = 'mani.manu-chaput.net'

# L'identifiant a utiliser avec son mot de passe
mySQLUserName = 'teleinfo'
mySQLPassWord='chaput'

# La base de donnees
mySQLDataBase = 'Domotique'

# La table (WARNING : pas utilise !)
mySQLTable = 'teleinfo'

#-------------------------------------------------------------
# Le serveur web
#-------------------------------------------------------------

#-------------------------------------------------------------
# Les logs
#-------------------------------------------------------------

# Pour afficher les messages sur la console
logConsole=False

# Le fichier de log
teleinfoLogFile='/var/log/teleinfo.log'

# Nombre de trames enregistrees dans la base de donnes
# avant d'envoyer un message dans les log
nbFrameMsgLog = 1000

#-------------------------------------------------------------

from flask import Flask, url_for, render_template, redirect, Response
import json
import sys, time, datetime
import copy
import threading, Queue
import mysql.connector
from mysql.connector import errorcode
import logging
import signal, sys
import argparse
#-------------------------------------------------------------

#=============================================================
# Les variables globales
#=============================================================
app = Flask(__name__)

#-------------------------------------------------------------
# Le tableau associatif teleinfo contient les informations lues
# dans la derniere trame analysee.
#-------------------------------------------------------------
teleinfo = {}

# Je ne vois pas comment ne pas faire du fd une variable globale
# tant qu'il est manipule par les fonctions de gestion du web
fd=0

# Pour declencher un arret
shutDown = False

# Les identifiants des threads
threadLecture = {}
threadSauvegarde = {}

# La connexion a la base de donnnees
database = {}

#=============================================================

#-------------------------------------------------------------
#    Le handler permettant une terminaison propre
#-------------------------------------------------------------
def signal_handler(signal, frame):
   global shutDown
   global threadLecture
   global threadSauvegarde

   logging.info("Arret en cours")

   # On previent les threads
   shutDown = True

   # On attend qu'ils se terminent
   if (useThread) :
      if (threadLecture.is_alive()) :
         threadLecture.join()
      if (threadSauvegarde.is_alive()) :
         threadSauvegarde.join()

   logging.info("Thread finis")

   sys.exit(0)

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

   logging.info("Thread de scrutation des trames en cours")

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
         if ('frame'  in debug) :
            print "[teleinfoReadFrame] Je renvoie une trame datee : "
            print trame
            print "------------------------------------"
         return {'trame': trame, 'datetime' : datetime.datetime.now()}
      # Sinon on insere dans la file
      else : 
         if ('frame'  in debug) :
            print "[teleinfoReadFrame] J'insere une trame datee : "
            print trame
            print "------------------------------------"
         # WARNING un try catch sur l'insertion
         try :
            fileDeTrames.put({'trame': trame, 'datetime' : datetime.datetime.now()})
         except :
            logging.error("Probleme d'insertion :" + sys.exc_info()[0])

         # S'il faut s'arreter, ...
         if (shutDown) :
            logging.info("Fin du thread de scrutation des trames")
            return
  
#-------------------------------------------------------------
#   Lecture d'une trame que l'on va transformer en dictionnaire
# dans la variable teleinfo qui est renvoyee.
#   Si une des sommes de controle est erronee, on renvoie None
#------------------------------------------------------------- 
def parseFrameToTeleinfo(frame) :
   ti = {}
   for line in frame.split('\n') :
      if (len(line) > 0 ) :
         # Calcul du checksum
         somme = 0
         for c in range(0, len(line) -3) :
            #logging.error("    On ajoute "+line[c] + " = " + str(ord(line[c]))+" a "+str(somme))
            somme += ord(line[c])
         somme = (somme & 0x3F) + 0x20

         if (somme != ord(line[len(line) -2])) :
            logging.error("parseFrameToTeleinfo : frame error")
            logging.error("   Line : " + line)
            logging.error("   somme : " + str(somme) + " != " + line[len(line)-2])

            return None

         # Construction du dictionnaire
         mots = line.split(' ')
         ti[mots[0]] =  mots[1]
         if (not (mots[0] in clefsContrat)) :
            logging.error("parseFrameToTeleinfo : clef " + mots[0] + " inconnue")
            return None

#         sys.stdout.write("[" + mots[0] + "] = {" + mots[1] + "} - " + mots[2] + "\n")
#      else :
#          logging.info("parseFrameToTeleinfo : short line !");

   # Tester si elle est bonne (toutes les lignes presentes)
   for clef in clefsContrat :
      if (not (clef in ti)) :
         logging.error("parseFrameToTeleinfo :clef " + clef + " manquante")
         return None

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
         host=mySQLServer,
         user=mySQLUserName,
         password=mySQLPassWord,
         database=mySQLDataBase)

   except mysql.connector.Error as err:
      if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
         logging.fatal("connectMySQL : Erreur d'authentification")
      elif err.errno == errorcode.ER_BAD_DB_ERROR:
         logging.fatal("connectMySQL : Base inconnue")
      else:
         logging.fatal("connectMySQL : Erreur d'acces a la base "+str(err.errno))
      return
   else:
      if ('mysql' in debug) :
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

   try :
      if ('mysql' in debug):
         logging.info("[insertTeleinfoMySQL] va inserer dans la base")
      cursor.execute(addTeleinfo, dataTeleinfo)
      if ('mysql' in debug):
         logging.info( "[insertTeleinfoMySQL] insertion faite")
   except :
      erreur = sys.exc_info()
      logging.error("insertTeleinfoMySQL : mySQL errno "+ erreur)

#-------------------------------------------------------------
# Recuperation du dernier enregistrement dans une structure
# teleinfo
#-------------------------------------------------------------
def getLastTeleinfo(dbCnx) :
   result = {}
 
   cursor = dbCnx.cursor()

   requete = ("SELECT * FROM teleinfo ORDER BY date, time LIMIT 1")
   cursor.execute(requete)

   for row in cursor :
      result = copy.deepcopy(row)
#      result['time'] = row['time'] # Bizzarement le time est reconnu en delta

   return result

#-------------------------------------------------------------
# Traitement d'une trame horodatee. Elle est transformee en
# une teleinfo. Elle est inseree dans la base de donnees et
# remplace la teleinfo en cours (variable globale)
#-------------------------------------------------------------
def processOneFrame(tr, dbCnx) :
   global teleinfo
   if ('frame' in debug) :
      print "[processOneFrame] J'ai une trame"

   if (useMySQL) :
      cursor = dbCnx.cursor()

   # on analyse la trame
   ti = parseFrameToTeleinfo(frame = tr['trame'])

   if (ti != None) :
      # On la tag avec sa date et heure (WARNING : a faire dans parseFrameToTeleinfo)
      estampille = tr['datetime']
      ti['DATE'] = estampille.date()
      ti['TIME'] = estampille.time()

      # Ca devient la teleinfo "active"
      if ('frame' in debug) :
         logging.info("[processOneFrame] On va copier")
      teleinfoLock.acquire()
      teleinfo = copy.deepcopy(ti)
      teleinfoLock.release()
      if ('frame' in debug) :
         logging.info("[processOneFrame] On va inserer")

      # On l'insere dans la BD
      if (useMySQL) :
         if ('mysql' in debug) :
            print "[processOneFrame] Je la mets dans la base"
         insertTeleinfoMySQL(cursor, ti) # ICI ?
         if ('mysql' in debug) :
            logging.info("[processOneFrame] On va commiter")
         dbCnx.commit()
      if ('frame' in debug) :
         logging.info("[processOneFrame] Et voilou")

#-------------------------------------------------------------
# Traitement continu de la file des trames horodatees
#-------------------------------------------------------------
def frameQueueProcess(fileDeTrames, dbCnx) :
   nbFrames = 0

   logging.info("Thread de traitement des donnees en cours")

   while (True) :
      # On va chercher une {trame, datetime} dans la file
      if ('frame' in debug) :
         print "[frameQueueProcess] J'attends une trame"
      try :
         tr = fileDeTrames.get(True)
      except :
         logging.error("Probleme d'extraction :" + sys.exc_info()[0])

      if ('frame' in debug) :
         print "[frameQueueProcess] J'ai une trame :"
         print tr['trame']
         print "------------------------------------"

      processOneFrame(tr, dbCnx)
 
      if ('frame' in debug) :
         logging.info("[frameQueueProcess] J'ai fini de processer")

      nbFrames = nbFrames + 1
      if (nbFrames == nbFrameMsgLog) :
         logging.info("frameQueueProcess : " + str(nbFrameMsgLog) + " frames processed")
         nbFrames = 0

      # S'il faut s'arreter, ...
      if (shutDown) :
         logging.info("Fin du thread de traitement des donnees")
         return

#-------------------------------------------------------------
# Calcul de la puissance consommee entre deux dates.
#
#  Input:
#  dateDebut et dateFin sont des dates
#  timeDebut et timeFin ...
#
#  Output :
#  Un dictionnaire est renvoye qui contient les clefs suivantes
#  'dateDebut' 'timeDebut' 'dateFin' 'timeFin'
#  'bbrhcjb' 'bbrhpjb' 'bbrhcjw' 'bbrhpjw' 'bbrhcjr' 'bbrhpjr'
#
#  Attention, les dates fournies correspondent au premier
#  echantillon apres la date de debut souhaitee et au dernier
#  avant la date de fin. Ce ne sont donc probablement pas
#  exactement les memes que celles en input
#-------------------------------------------------------------
def puissanceCumulee(dbCnx, dateDebut, timeDebut, dateFin, timeFin) :
   cursor = dbCnx.cursor(dictionary=True)

   # On cherche le dernier avant la date de fin
#   print "On cherche le dernier avant fin : "+ timeFin.strftime("%X") + " : "+ dateFin.strftime("%x")
   requete = ("SELECT * FROM teleinfo WHERE ( date < %s ) OR ((date = %s) AND ( time <= %s )) ORDER BY date DESC, time DESC LIMIT 1")
   cursor.execute(requete, (dateFin, dateFin, timeFin))

   for row in cursor :
      dateFin=row['date']
      timeFin=(datetime.datetime.combine(dateFin, datetime.time()) + row['time']).time() # Bizzarement le time est reconnu en delta
      bbrhcjb=row['bbrhcjb']
      bbrhpjb=row['bbrhpjb']
      bbrhcjw=row['bbrhcjw']
      bbrhpjw=row['bbrhpjw']
      bbrhcjr=row['bbrhcjr']
      bbrhpjr=row['bbrhpjr']
#   print "On trouve a "+dateFin.strftime("%x")+" - "+timeFin.strftime("%X") + " :"
#   print bbrhcjb
#   print bbrhpjb
#   print bbrhcjw
#   print bbrhpjw
#   print bbrhcjr
#   print bbrhpjr

   # On cherche le premier apres la date de debut
#   print "On cherche le premier apres le depart : "+ timeDebut.strftime("%X") + " : "+ dateDebut.strftime("%x")
   requete = ("SELECT * FROM teleinfo WHERE (( date = %s ) AND ( time >= %s ) OR (date > %s)) ORDER BY date, time LIMIT 1")
   cursor.execute(requete, ( dateDebut, timeDebut, dateDebut))

   for row in cursor :
      dateDebut=row['date']
      timeDebut=(datetime.datetime.combine(dateDebut, datetime.time()) + row['time']).time() # Bizzarement le time est reconnu en delta
      bbrhcjb-=row['bbrhcjb']
      bbrhpjb-=row['bbrhpjb']
      bbrhcjw-=row['bbrhcjw']
      bbrhpjw-=row['bbrhpjw']
      bbrhcjr-=row['bbrhcjr']
      bbrhpjr-=row['bbrhpjr']

   cursor.close()

   return {'dateDebut' : dateDebut, 'timeDebut' : timeDebut, 'dateFin' : dateFin, 'timeFin' : timeFin, 'bbrhcjb' : bbrhcjb, 'bbrhpjb' : bbrhpjb, 'bbrhcjw' : bbrhcjw, 'bbrhpjw' : bbrhpjw, 'bbrhcjr' : bbrhcjr, 'bbrhpjr' : bbrhpjr}

#=============================================================
# Gestion de l'interface web
#=============================================================
#-------------------------------------------------------------
# La page principale
#-------------------------------------------------------------
@app.route("/")
def accueil():
   global database  # Comment faire autrement ?

   # Pour le moment la premiere page ne contient rien !
   templateData = {
      'version' : teleinfoVersion,
      'class_acc': 'active',
      'class_ins': 'inactive',
      'class_jou': 'inactive',
      'class_con': 'inactive',
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

#--------------------------------------------------------
#   La consommation sur une journee
#--------------------------------------------------------
@app.route("/consojournaliere/<when>")
def consojournaliere(when) :
   valeurs = {
      'BBRHPJB' : {'nom' : 'Pl. bleu', 'conso' : [] },
      'BBRHCJB' : {'nom' : 'Cr. bleu', 'conso' : [] },
      'BBRHPJW' : {'nom' : 'Pl. blanc', 'conso' : [] },
      'BBRHCJW' : {'nom' : 'Cr. blanc', 'conso' : [] },
      'BBRHPJR' : {'nom' : 'Pl. rouge', 'conso' : [] },
      'BBRHCJR' : {'nom' : 'Cr. rouge', 'conso' : [] }
   } 

   # Definition des creneaux horaires pour l'axe des X
   creneaux = []

   # On fait des requetes sur les dernieres 24h. Une requete
   # par creneau de 1h
   if (when == 'last') :
      debut = datetime.datetime.now() - datetime.timedelta(days = 1)
      title = 'Consommation sur les denieres 24 heures'
   elif (when == 'today') :
      debut = datetime.datetime.now()
      debut = debut.replace(hour = 0, minute=0, second=0, microsecond=0)
      title = 'Consommation de la journee ('+debut.strftime("%x")+")"
   elif (when == 'yesterday') :
      debut = datetime.datetime.now()- datetime.timedelta(days = 1)
      debut = debut.replace(hour = 0, minute=0, second=0, microsecond=0)
      title = 'Consommation hier'
   else :
      logging.error("consojournaliere : parametre "+when+" inconnu");
      render_template("error.html")
      return

   # On commence sur une heure pleine
   debut = debut.replace(minute=0, second=0, microsecond=0)

   for c in range (0, 24) :
      fin = debut + datetime.timedelta(hours = 1)
      if (fin < datetime.datetime.now()) :  # On ne fait que des creneaux ecoules !
         pui = puissanceCumulee(database, debut.date(), debut.time(), fin.date(), fin.time())
         creneaux.append(debut.strftime("%H:%M"))
         if ('web' in debug) :
            logging.info("Entre " + debut.strftime("%x, %X") + " et " + fin.strftime("%x, %X") + " : ")
            logging.info(str(pui['bbrhpjb'])+"/"+str(pui['bbrhcjb'])+"/"+str(pui['bbrhpjw'])+"/"+str(pui['bbrhcjw'])+"/"+str(pui['bbrhpjr'])+"/"+str(pui['bbrhcjr']))
         valeurs['BBRHPJB']['conso'].append(str(pui['bbrhpjb']))
         valeurs['BBRHCJB']['conso'].append(str(pui['bbrhcjb']))
         valeurs['BBRHPJW']['conso'].append(str(pui['bbrhpjw']))
         valeurs['BBRHCJW']['conso'].append(str(pui['bbrhcjw']))
         valeurs['BBRHPJR']['conso'].append(str(pui['bbrhpjr']))
         valeurs['BBRHCJR']['conso'].append(str(pui['bbrhcjr']))
      else :
         valeurs['BBRHPJB']['conso'].append(0)
         valeurs['BBRHCJB']['conso'].append(0)
         valeurs['BBRHPJW']['conso'].append(0)
         valeurs['BBRHCJW']['conso'].append(0)
         valeurs['BBRHPJR']['conso'].append(0)
         valeurs['BBRHCJR']['conso'].append(0)
      debut = fin

   templateData = {
      'version' : teleinfoVersion,
      'class_acc': 'inactive',
      'class_ins': 'inactive',
      'class_jou': 'active',
      'class_con': 'inactive',
      'version'  : teleinfoVersion,
      'creneaux' : creneaux,
      'title'    : title,
      'valeurs'  : valeurs
   }
   return render_template('consojournaliere.html', **templateData)
   
#=============================================================
#
#=============================================================

# Gestion des parametres
parser = argparse.ArgumentParser()
parser.add_argument("-t", "--no_thread", help="pas de Threads",
                    action="store_true")
parser.add_argument("-w", "--no_web", help="pas de web",
                    action="store_true")
parser.add_argument("-f", "--no_serial", help="pas de lecture de trames",
                    action="store_true")
parser.add_argument("-l", "--log_console", help="log sur la console",
                    action="store_true")

# On traite les options
args = parser.parse_args()
if (args.no_thread) :
   useThread = False

if (args.no_web) :
   runWebServer = False

if (args.no_serial) :
   readFrames = False

if (args.log_console) :
   logConsole = True

# Pour terminer (par ^C)
signal.signal(signal.SIGINT, signal_handler)

# Pour sigterm utilise par start-stop-daemon
signal.signal(signal.SIGTERM, signal_handler)

# Configuration du systeme de log
if (logConsole) :
   logging.basicConfig(format='%(asctime)s - %(levelname)s:%(message)s',
                       level=logging.DEBUG)
else :
   logging.basicConfig(filename=teleinfoLogFile,
                       format='%(asctime)s - %(levelname)s:%(message)s',
                       level=logging.DEBUG)

logging.info("Teleinfo version " + teleinfoVersion + " running")

# Initialisation du port serie
fd=initSerialPort();

# Connexion a la base de donnees
if (useMySQL) :
   database = connectMySQL()
else :
   logging.info("Pas de base de donnees")
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
   logging.info("Pas de threads")
   if (readFrames) :
      tr = teleinfoReadFrame(fd, True)
      processOneFrame(tr, database)

# On demarre le serveur web
if __name__ == "__main__":
   if (runWebServer) :
      logging.info("Lancement du serveur web")
      # Attention, pas de debug en multithreads
      app.run(host='0.0.0.0', port=8081, debug=True)
   # Sinon, on attend la fin des threads
   else :
      logging.info("Pas de serveur web")
      if (useThread) :
         threadSauvegarde.join()
   # Sinon on ne fait rien !
