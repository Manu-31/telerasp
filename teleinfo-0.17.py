#=============================================================
#   Une premiere tentative de manipulation des trames teleinfo
#
#   1 - Structure generale
#   (voir aussi le dessin principe.odg qui illutre la chose)
#
#   Ce programme cree des threads pour la lecture, l'archivage
#   et l'affichage des donnees. L'idee est d'avoir dans un
#   seul programme tous les outils, mais ne de pas necessairement
#   les utiliser simultanement.
#
#   Le role de chacun des threads est le suivant
#
#   . Le premier passe son temps a lire des trames sur le port
#   serie et les stocke dans une file de trames horodatees de
#   type Queue : frameQueue. La fonction qu'il execute est
#   teleinfoReadFrame
#
#   . Le deuxieme passe son temps a les consommer dans la Queue
#   et a les transformer en teleinfo puis les envoyer dans une
#   autre file (teleinfoQueue) destinee a de la sauvegarde et/ou
#   a les integrer dans les donnees locales pour affichage.
#
#   . Le troisieme thread execute la fonction saveTeleinfo
#   dont le boulot est de sauvegarder les donnees (pour le
#   moment par envoie dans une bd via du sql).
#
#   . Le quatrieme va chercher des donnees sauvegardees
#   pour mettre a jour les donnees locales pour affichage.

#   Chaque teleinfo remplace la precedente dans
#   la variable globale du meme nom. Ainsi les autres threads
#   disposent toujours dans cette variable des informations
#   les plus a jour.
#
#   2 - Principaux "types"
#
#   . Les trames lues par teleinfoReadFrame sont codees comme
#   une simple chaine de caracteres
#
#   . Les trames horodatees sont stoquees dans la file sous
#   la forme d'un dictionnaire {'trame': trame, 'datetime' :
#   datetime.datetime.now()}
#
#   . La structure teleinfo utilisee pour stocker les informations
#   d'une trame est un tableau associatif contenant tous les
#   champs de la trame plus un champ 'date' et un champ 'time'
#   construits a partir de la date de capture de la trame
#   stockee avec elle dans la Queue. A partir de la version 0.10
#   les clefs sont en minuscules !
#
#   . Une structure summary est un dictionnaire avec les clefs
#   suivantes
#     - nbMax est le nombre max de series voulues
#     - startTime est la date de debut de la premiere serie
#     - serieDelta est la duree entre deux (debuts de) series
#     - duration est un timedelta qui donne la duree sur laquelle
#   s'etalent les mesures d'une serie
#     - step est un timedelta qui donne la periode de mesure
#     - series est une serie de mesures sous la forme d'un
#   dictionnaire avec
#         . date est un time de la premiere mesure
#         . title est un titre
#         . data est une liste des mesures
#-------------------------------------------------------------
#   WARNING : 
#   - A faire
#     . supprimer les hourly si pas de web, non ?
#     . ajouter un debug flag queue 
#     . Ajouter une option de choix du fichier de conf
#     . Un cache des donnees des pages !
#     . differents modes de debug configures par le fichier
#     . une page de config, meme sans edition
#     . un fichier de configuration (qui permettra un comportement
#     different pour root !) avec ConfigParser
#     . les urls dans les pages web
#     . s'assurer que ca fonctionne meme en cas de panne du
#     serveur de base de donnees
#     . gerer les erreurs internes, avec un try catch sur les
#     pages web en traitant l'exception KeyError par exemple
#   FAIT
#     . Passer les clefs des teleinfo en minuscule
#     . calcul du checksum
#     . gerer la fin du processus !
#     . un fichier de log, pour voir l'etat (utiliser la classe
#     logger)
#     . Pourquoi les trames sont parfois erronees ?
#       Apparemment ca viendrait du mode debug de flask
#=============================================================
teleinfoVersion = "0.17"    # Restructuration des threads
                            # Sauvegarde par batch (max nbMaxBeforeCommit)

#teleinfoVersion = "0.16"   # Au boulot sur le web
                            # Support de lecture erronee d'un caractere 
#teleinfoVersion = "0.15"   # Traitement des cas d'erreur afin d'etre
                            # robuste face aux soucis d'acces a la BD
                            # remplacement de certains print par du log
#teleinfoVersion = "0.14"   # On ne se connecte a la base SQL que
                            # lorsque necessaire
#teleinfoVersion = "0.13"   # On passe a MySQLdb
#teleinfoVersion = "0.12"   # Fusion de useThread et useDataBase
                            # dans populateDataBase
                            # Ajout du fichier de configuration
#teleinfoVersion = "0.11"   # Ajouts mineurs
#teleinfoVersion = "0.10"   # Passage des clefs en minuscules
                            # Decompte des trames erronnees
#teleinfoVersion = "0.9"    # Premiere vraie page depuis la BD
                            # Ajout de l'option -l
                            # Ajout de la verification des trames
                            # Introduction d'un debug thematique
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
debugFlags={
#   'serial',   # Sur le port serie
#   'bytes',    # Octet par octet !
#   'frame',    # La gestion des trames
#   'dumpframe',# Le contenue des trames
#   'web',      # L'affichage de pages
#   'mysql'     # L'acces a la BD
}

# Pour debugage Flask. ATTENTION, c'est icompatible
# avec l'utilisation du port serie (en fait il faudrait
# verifier le lock ...)
debugFlask=True   # ok

# Si le booleen suivant est vrai, deux threads sont lancees
# pour capturer des donnees et les stocker dans la base de
# donnees (voir plus haut la structure).
populateDataBase = True

# Faut-il lancer le serveur Web ?
runWebServer = True # ok

# Peut-on faire des lectures de trame ?
# La valeur False n'a d'interet que pour le debogage pour le
# moment. Il pourra servir a faire un serveur web qui ne lit
# pas de valeur instantanee, pendant qu'un autre processus ne 
# fera que de la lecture sans service web.
readFrames=True # ok

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

# Tarifs horaires (au 01/05/2013) OK
tarifs = {
   'hcjb' : 0.0763,
   'hpjb' : 0.0907,
   'hcjw' : 0.1074,
   'hpjw' : 0.1272,
   'hcjr' : 0.1971, 
   'hpjr' : 0.5119
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

# La gestion du backlog
backlogMin = 20
dbSaveDelay = 60
nbMaxBeforeCommit = 100         

#-------------------------------------------------------------
# Le serveur web
#-------------------------------------------------------------
availableThemes = {'default', 'dark-blue', 'dark-green',
                   'dark-unica', 'gray',  'grid',  'grid-light',
                   'sand-signika', 'skies'}
themeActuel="dark-green"
webPort=8081

#-------------------------------------------------------------
# Les logs
#-------------------------------------------------------------

# Pour afficher les messages sur la console
logConsole=False

# Le fichier de log
logFile='/var/log/teleinfo.log'

# Nombre de trames enregistrees dans la base de donnes
# avant d'envoyer un message dans les log
nbFrameMsgLog = 1000

#-------------------------------------------------------------

from flask import Flask, url_for, render_template, redirect, Response
import json
import sys, time, datetime
import copy
import threading, Queue
import MySQLdb
#import mysql.connector
#from mysql.connector import errorcode
import logging
import signal, sys
import argparse
import string
import ConfigParser, os

#-------------------------------------------------------------

#=============================================================
# Les variables globales
#=============================================================
app = Flask(__name__)

#-------------------------------------------------------------
# Le tableau associatif teleinfoCourante contient les informations
# lues dans la derniere trame analysee.
#-------------------------------------------------------------
teleinfoCourante = {}

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

# Le nombre de trames traitees
nbFrames = 0

# Le nombre de trames non traitees pour erreur
nbTramesErronnees = 0

# Le cache des mesures a afficher
summaries = [
   # Moyenne horaire sur une journee pendant la derniere semaine
   # permet de voir l'evolution de la conso quotidienne sur la
   # semaine
   {
      'name' : 'last-week',
      'startTime' : datetime.timedelta(days=-7),
      'duration' : datetime.timedelta(days=1),
      'step' : datetime.timedelta(hours=1),
      'nbMax' : 7,
      'series' : {}
   }
   # Moyenne horaire sur une tranche horaire donnee sur les
   
]

#=============================================================
#                 LES FONCTIONS GENERALISTES
#=============================================================

#-------------------------------------------------------------
#    Le handler permettant une terminaison propre
#-------------------------------------------------------------
def signal_handler(signal, frame):
   global shutDown
   global threadLecture
   global threadSauvegarde

   logging.info("[signal_handler} signal recu, Arret en cours")

   # On previent les threads
   shutDown = True

   # On attend qu'ils se terminent
   if (populateDataBase) :
      if (threadLecture.is_alive()) :
         threadLecture.join()
      if (threadSauvegarde.is_alive()) :
         threadSauvegarde.join()

   logging.info("Thread finis")

   sys.exit(0)

#=============================================================
#          LES FONCTIONS DE GESTIONS DES TRAMES
#=============================================================

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
#   Lecture de trames depuis l'interface serie. Cette fonction
# passe son temps a lire une trame sur le port d'entree puis
# a l'inserer dans la file des trames.
#   Elle s'arrete si shutDown est vrai
#-------------------------------------------------------------
def teleinfoReadFrame(fd, frameQueue):
   import os
   c = "x"

   if ('thread' in debugFlags) :
      logging.info("[teleinfoReadFrame] starting")

   # On lit sans s'arreter (il y aura un return si oneShot)
   while (True) :
      if ('serial' in debugFlags) :
         logging.info("[teleinfoReadFrame] reading a frame from "+ devicePath)

      cp = c
      c = os.read(fd, 1)
#      sys.stdout.write(hex(ord(c)) + " ")
#      n = 0

#      print("On attend la fin de la trame en cours\n")
      while (c and ((not((ord(c) == 0x02) and (ord(cp) == 0x03))))) :   # Attention si lecture ratee c nulle
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
      while (c and (not(ord(c) == 0x03))) :   # Attention si lecture ratee c nulle
         trame = trame + c
         cp = c
         c = os.read(fd, 1)

      if ('serial' in debugFlags) :
         logging.info("[teleinfoReadFrame] frame built from "+ devicePath)

      if ('frame'  in debugFlags) :
         logging.info("[teleinfoReadFrame] J'insere une trame datee : ")
         if ('dumpframe'  in debugFlags) :
            logging.info(trame)
            logging.info("------------------------------------")
      # WARNING un try catch sur l'insertion
      try :
         frameQueue.put({'trame': trame, 'datetime' : datetime.datetime.now()})
         if ('frame'  in debugFlags) :
            logging.info("[teleinfoReadFrame] File de taille "+ str(frameQueue.qsize()))
      except :
         logging.error("[teleinfoReadFrame] Probleme d'insertion :" + sys.exc_info()[0])

       # S'il faut s'arreter, ...
      if (shutDown) :
         if ('thread' in debugFlags) :
            logging.info("[teleinfoReadFrame] shutting down")
         return
  
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
   print "Type de contrat   : " + ti['optarif']
   print "Couleur de demain : " + ti['demain']
   print "Tarif en cours    : " + ti['ptec']
   print "Intensite         : " + ti['iinst']
   print "Puissance app     : " + ti['papp']
   
#-------------------------------------------------------------
#    Traitement continu de la file des trames horodatees
# Ce sous programme tourne en permanence dans un thread. Il
# passe son temps a lire les trames dans la 'fileDeTrames'.
#
#    Il les converti en teleinfo et les envoie au fur et a
# mesure a la fonction de mise a jour des donnees et/ou il
# les passe au thread de sauvegarde
#-------------------------------------------------------------
def frameQueueProcess(fileDeTrames, teleinfoQueue) :
   global shutDown
   global populateDataBase

   if ('thread' in debugFlags) :
      logging.info("[frameQueueProcess] Starting")

   while (True) :
      # On va chercher une {trame, datetime} dans la file
      if ('frame' in debugFlags) :
         logging.info("[frameQueueProcess] J'attends une trame (file de longueur "+str(frameQueue.qsize())+")")
      try :
         tr = frameQueue.get(True)
      except :
         logging.error("Probleme d'extraction :" + sys.exc_info()[0])

      if ('frame' in debugFlags) :
         logging.info("[frameQueueProcess] J'ai une trame :")
         if ('dumpframe' in debugFlags) :
            logging.info(tr['trame'])
         logging.info("------------------------------------")

      # Converion de la trame en question en teleinfo
      teleinfo = frameToTeleinfo(tr)
 
      if ('frame' in debugFlags) :
         logging.info("[frameQueueProcess] J'ai fini de processer")

      # Que fait-on de la teleinfo creee ?

      # Si on fait aussi office de web server, on met a jour les donnees
      if (runWebServer) :
         if ('frame' in debugFlags) :
            logging.info("[frameQueueProcess] On met a jour les donnees pour le web")
         updateData(teleinfo)

      # Si on peuple la base de donnees, on envoie
      if (populateDataBase):
         if ('frame' in debugFlags) :
            logging.info("[frameQueueProcess] On insere dans la file de teleinfo (taille "+ str(teleinfoQueue.qsize())+")")
         try :
            teleinfoQueue.put(teleinfo)
            if ('frame' in debugFlags) :
               logging.info("[frameQueueProcess] Insertion faite")
         except :
            logging.error("[teleinfoReadFrame] Probleme d'insertion :" + sys.exc_info()[0])

      # S'il faut s'arreter, ...
      if (shutDown) :
         logging.info("Fin du thread de traitement des donnees")
         return

#=============================================================
#         FONCTIONS LIEES A LA BASE DE DONNEES
#=============================================================

#-------------------------------------------------------------
# Connexion a la base mySQL.
# Valeur de retour :
#    une connexion en  cas de succes
#    None en cas d'echec
#-------------------------------------------------------------
def connectMySQL() :
   
   if ('mysql' in debugFlags) :
      logging.info("[connectMySQL] Connexion en cours ...")
   try:
      connexion = MySQLdb.connect(
         host=mySQLServer,
         user=mySQLUserName,
         passwd=mySQLPassWord,
         db=mySQLDataBase)
      if ('mysql' in debugFlags) :
         logging.info("[connectMySQL] Connecte a la base")

   except MySQLdb.Error, e:
      connexion = None
      logging.error( "[connectMySQL] Error [%d]: %s" % (e.args[0], e.args[1]))
   finally :
      if ('mysql' in debugFlags) :
         logging.info("[connectMySQL] Fin de connexion ...")
      return connexion 

#-------------------------------------------------------------
# Insertion d'un jeu de mesure dans la base mySQL
#-------------------------------------------------------------
def insertTeleinfoMySQL(ti, cursor) :
   addTeleinfo =  ("INSERT INTO teleinfo "
                   "(date, time, adco, optarif, isousc, bbrhcjb, bbrhpjb, bbrhcjw, bbrhpjw, bbrhcjr, bbrhpjr, ptec, demain, iinst, imax, papp, hhphc, motdetat) "
                   "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
   dataTeleinfo = (
      ti['date'],
      ti['time'],
      ti['adco'],
      ti['optarif'],
      ti['isousc'],
      ti['bbrhcjb'],
      ti['bbrhpjb'],
      ti['bbrhcjw'],
      ti['bbrhpjw'],
      ti['bbrhcjr'],
      ti['bbrhpjr'],
      ti['ptec'],
      ti['demain'],
      ti['iinst'],
      ti['imax'],
      ti['papp'],
      ti['hhphc'],
      ti['motdetat']
   )

   if ('mysql' in debugFlags):
      logging.info("[insertTeleinfoMySQL] va inserer dans la base")

   try :
      # On insere dans la base
      cursor.execute(addTeleinfo, dataTeleinfo)

   except MySQLdb.Error :
      logging.error("[insertTeleinfoMySQL] : erreur MySQL")

   if ('mysql' in debugFlags) :
      logging.info("[insertTeleinfoMySQL] : Termine ...")

#-------------------------------------------------------------
# Recuperation depuis la base de donnees du dernier
# enregistrement dans une structure teleinfo. Cette fonction
# est utilisee par webGetLastTeleinfo() lorsqu'il n'est pas
# possible de lire une trame sur le device (lorsque readFrames
# est a False).
#-------------------------------------------------------------
def getLastTeleinfoFromDataBase() :
   result = {}

   try :
      if ('mysql' in debugFlags):
         logging.info("[getLastTeleinfoFromDataBase] connexion a la base")
      dbCnx = connectMySQL()
      if (dbCnx is None) :
         logging.error("[getLastTeleinfoFromDataBase] impossible de se connecter")
         return None
      if ('mysql' in debugFlags):
         logging.info("[getLastTeleinfoFromDataBase] creation du curseur")
      cursor = dbCnx.cursor(MySQLdb.cursors.DictCursor)
      requete = ("SELECT * FROM teleinfo ORDER BY date DESC, time DESC LIMIT 1")
      if ('mysql' in debugFlags):
         logging.info("[getLastTeleinfoFromDataBase] execution de la requete")
      cursor.execute(requete)

      for row in cursor :
         result = copy.deepcopy(row)
#      result['time'] = row['time'] # Bizzarement le time est reconnu en delta

#   except MySQLdb.Error as e:
   except :
      logging.error("[getLastTeleinfoFromDataBase] : mySQL err")

   finally :
      if ('mysql' in debugFlags):
         logging.info("[getLastTeleinfoFromDataBase] : bon, ben on ferme !")
      cursor.close()
      dbCnx.close()

   return result

#-------------------------------------------------------------
#   Cette fonction passe son temps a consommmer des teleinfo
# presentes dans la file teleinfoQueue et les sauvegarder.
#    Pour le moment (et surement pour longtemps) cette
# sauvegarde ne peut etre que l'insertion dans une BD via mySQL.
#-------------------------------------------------------------
def saveTeleinfo(teleinfoQueue):
   global shutDown
   global nbMaxBeforeCommit

   if ('thread' in debugFlags) :
      logging.info("[saveTeleinfo] Starting")

   while (not shutDown) :
      # On attend d'avoir au moins backlogMin info a sauvegarder
      while (teleinfoQueue.qsize() < backlogMin):
         if ('frame' in debugFlags) :
            logging.info("[saveTeleinfo] file de longueur "+str(teleinfoQueue.qsize())+" trop courte, j'attends")
         time.sleep(dbSaveDelay)

      # On se connecte a la BD
      if ('mysql' in debugFlags):
         logging.info("[saveTeleinfo] connexion a la base")

      dbCnx = connectMySQL()

      if (dbCnx is not None) : # Si ca a marche
         # On essaie de creer un curseur 
         if ('mysql' in debugFlags):
            logging.info("[saveTeleinfo] creation du curseur")
         cursor = dbCnx.cursor()

         nbInsert = 0
         # On vide la file dans la connexion
         while ((teleinfoQueue.qsize() > 0) and (nbInsert < nbMaxBeforeCommit)):

            # On va chercher une teleinfo
            if ('frame' in debugFlags) :
               logging.info("[saveTeleinfo] J'attends une trame (lg "+str(teleinfoQueue.qsize())+" et "+str(nbInsert)+"/"+str(nbMaxBeforeCommit)+" a commit)")
            try :
               ti = teleinfoQueue.get(False)

               logging.info("[saveTeleinfo] OK, on l'envoie")

               # On l'insere dans la BD
               insertTeleinfoMySQL(ti, cursor)
               nbInsert = nbInsert + 1

               logging.info("[saveTeleinfo] C'est fait")

            except Queue.Empty :
               logging.error("[saveTeleinfo] C'est bon j'ai vide la file !")

         # C'est fini, on commit
         if ('mysql' in debugFlags):
            logging.info( "[saveTeleinfo] insertion faite, on passe au commit")

         dbCnx.commit()

         if ('mysql' in debugFlags) :
            logging.info("[saveTeleinfo] Commit done")

         # L'affaire est pliee, on ferme la connexion
         if (not (dbCnx is None)) :
            if ('mysql' in debugFlags) :
               logging.info("[saveTeleinfo] : on ferme le curseur ...")
            cursor.close()
            if ('mysql' in debugFlags) :
               logging.info("[saveTeleinfo] : on ferme la connexion ...")
            dbCnx.close()
         if ('mysql' in debugFlags) :
            logging.info("[saveTeleinfo] : connexion closed ...")

      else : # Si c'est rate, on essaiera plus tard
         if ('mysql' in debugFlags):
            logging.info("[saveTeleinfo] connexion impossible on essaiera plus tard ...")
            logging.info("[saveTeleinfo] : On attend "+str(dbFailedDelay)+" secondes avant de re-essayer")
         time.sleep(dbFailedDelay)
         if ('mysql' in debugFlags):
            logging.info("[saveTeleinfo] Fin de l'attente, essayons a nouveau ...")

   if ('thread' in debugFlags) :
      logging.info("[saveTeleinfo] Stopping")

#=============================================================
#     FONCTIONS LIEES A LA GESTION DES DONNEES LOCALES
#=============================================================

#-------------------------------------------------------------
#   Mise a jour des donnees locales pour affichage
#-------------------------------------------------------------
def updateData(ti) :
   global teleinfoCourante

   dateLastHourlyUpdate = datetime.datetime.now() - datetime.timedelta(hours=1) 

   if ('data' in debugFlags) :
      logging.info("[updateData] Running ...")

   # Ca devient la teleinfoCourane "active" (WARNING  : a virer)
   if ('frame' in debugFlags) :
      logging.info("[debugFlags] On va copier")

   teleinfoLock.acquire()
   teleinfoCourante = copy.deepcopy(ti)
   teleinfoLock.release()

   if ('frame' in debugFlags) :
      logging.info("[debugFlags] Et voilou")

   # Faut-il mettre a jour un des tableaux d'affichage ?
   maintenant = datetime.datetime.now()
   if (maintenant >= dateLastHourlyUpdate + datetime.timedelta(hours=1)) :
       logging.info("dateLastHourlyUpdate : "+ dateLastHourlyUpdate.strftime("%x, %X")+" time to update !")
       hourlyUpdate()
       dateLastHourlyUpdate = maintenant.replace(minute=0, second=0, microsecond=0)

#-------------------------------------------------------------
# Mise a jour horaire des tableaux a afficher
#-------------------------------------------------------------
def hourlyUpdate() :
   if ('periodic' in debugFlags) :
      logging.info("[hourlyUpdate] Running ...")

   # On cherche les mesures horaires
   for summary in summaries :
      if ('periodic' in debugFlags) :
         logging.info("[hourlyUpdate] On passe a '"+summary['name'] + "' : "+str(len(summary['series'])) + "/" + str(summary['nbMax']) + " series")

      # 1 - On cherche la datetime exacte de la premiere mesure
      startTime = datetime.datetime.now() + summary['startTime']
      # On ne fait pas plus precis que la minute
      startTime = startTime.replace(second=0, microsecond=0)
      if (summary['step'].seconds % 3600 == 0) :
         startTime = startTime.replace(minute=0)
         if (summary['step'].seconds % (24*3600) == 0) :
            startTime = startTime.replace(hour=0)
      if ('periodic' in debugFlags) :
         logging.info("[hourlyUpdate] Ca commence a " + startTime.strftime("%x - %X"))

   if ('periodic' in debugFlags) :
      logging.info("[hourlyUpdate] Done !")


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
            if ('bytes' in debugFlags) :
               logging.info("    On ajoute '"+line[c] + "' = " + str(ord(line[c]))+" a "+str(somme))
            somme += ord(line[c])
         somme = (somme & 0x3F) + 0x20

         if (somme != ord(line[len(line) -2])) :
            logging.error("parseFrameToTeleinfo : frame error")
            logging.error("   Line : " + line)
            logging.error("   somme : " + str(somme) + " != " + str(ord(line[len(line)-2])))

            return None

         # Construction du dictionnaire
         mots = line.split(' ')
         ti[mots[0]] =  mots[1]
         if (not (mots[0] in clefsContrat)) :
            logging.error("parseFrameToTeleinfo : clef " + mots[0] + " inconnue")
            return None

   # Tester si elle est bonne (toutes les lignes presentes)
   for clef in clefsContrat :
      if (not (clef in ti)) :
         logging.error("parseFrameToTeleinfo :clef " + clef + " manquante")
         return None

   result= {}
   # On converti en minuscules (j'aime pas les majuscules !)
   for clef in ti :
      clefMin = string.lower(clef)
      result[clefMin] = ti[clef]

   return result

#-------------------------------------------------------------
# Traitement d'une trame horodatee. Elle est transformee en
# une teleinfo.
#-------------------------------------------------------------
def frameToTeleinfo(tr) :
   global nbTramesErronnees
   global nbFrames

   if ('frame' in debugFlags) :
      logging.info("[frameToTeleinfo] Une trame a traiter")

   # on analyse la trame
   ti = parseFrameToTeleinfo(frame = tr['trame'])

   if (ti != None) :
      # On la tag avec sa date et heure (WARNING : a faire dans parseFrameToTeleinfo)
      estampille = tr['datetime']
      ti['date'] = estampille.date()
      ti['time'] = estampille.time()

   else:
      logging.info('Trame erronnee ...')
      nbTramesErronnees += 1

   # On compte les frames et les erreurs
   nbFrames = nbFrames + 1
   if (nbFrames == nbFrameMsgLog) :
      logging.info("frameQueueProcess : " + str(nbFrameMsgLog) + " frames processed (" + str(nbTramesErronnees) + " errors)")
      nbFrames = 0
      nbTramesErronnees = 0

   if ('frame' in debugFlags) :
      logging.info("[frameToTeleinfo] Fin de traitement de la trame")

   return ti

#-------------------------------------------------------------
# Cette fonction passe son temps a lire les donnees depuis
# la sauvegarde et a mettre a jour les donnees locales
#-------------------------------------------------------------
def getData() :
   if ('thread' in debugFlags) :
      logging.info("[getData] starting")

   if ('thread' in debugFlags) :
      logging.info("[getData] shutting down")


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
#
#  WARNING on peut rationnaliser tout ca !!
#-------------------------------------------------------------
def puissanceCumulee(dateDebut, timeDebut, dateFin, timeFin) :

   try :
      if ('mysql' in debugFlags):
         logging.info("[puissanceCumulee] connexion a la base")
      dbCnx = connectMySQL()
      if ('mysql' in debugFlags):
         logging.info("[puissanceCumulee] creation du curseur")
      cursor = dbCnx.cursor(MySQLdb.cursors.DictCursor)

      # On cherche le dernier avant la date de fin
#   print "On cherche le dernier avant fin : "+ timeFin.strftime("%X") + " : "+ dateFin.strftime("%x")
      requete = ("SELECT * FROM teleinfo WHERE ( date < %s ) OR ((date = %s) AND ( time <= %s )) ORDER BY date DESC, time DESC LIMIT 1")

      if ('mysql' in debugFlags):
         logging.info("[puissanceCumulee] execution de la requete")

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

      if ('mysql' in debugFlags):
         logging.info("[puissanceCumulee] execution de la requete")

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

   except MySQLdb.Error as e:
      logging.error("[puissanceCumulee] : mySQL err")

   finally :
      logging.info("[puissanceCumulee] : on ferme ...")
      cursor.close()
      dbCnx.close()

   return {'dateDebut' : dateDebut, 'timeDebut' : timeDebut, 'dateFin' : dateFin, 'timeFin' : timeFin, 'bbrhcjb' : bbrhcjb, 'bbrhpjb' : bbrhpjb, 'bbrhcjw' : bbrhcjw, 'bbrhpjw' : bbrhpjw, 'bbrhcjr' : bbrhcjr, 'bbrhpjr' : bbrhpjr}

#=============================================================
# Gestion de l'interface web
#=============================================================

#-------------------------------------------------------------
# La fonction suivante permet d'obtenir la structure teleinfo
# la plus a jour possible. Pour cela, on utilise, par ordre de
# preference, la premiere technique disponible dans la liste
# suivante
# . la variable globale teleinfo mise a jour regulierement par
# le thread de lecture (si populateDataBase est vrai)
# . la lecture depuis la source (si readFrames est vrai)
# . la consultation de la base de donnees
#-------------------------------------------------------------
def webGetLastTeleinfo() :

   # Si on utilise les threads, on prend la derniere lue
   if (populateDataBase) :
      if ('web' in debugFlags) :
         logging.info('lireClefJSON : using threads')
      teleinfoLock.acquire()
      ti = copy.deepcopy(teleinfoCourante)
      teleinfoLock.release()
   else :
      # Si on peut au moins lire une trame ...
      if (readFrames) :
         if ('web' in debugFlags) :
            logging.info('lireClefJSON : using serial')
         tr = teleinfoReadFrame(fd, True)
         processOneFrame(tr)
         ti = teleinfoCourante      
      # Finalement si on ne peut rien on va dans la base
      else : 
         if ('web' in debugFlags) :
            logging.info('lireClefJSON : using database')
         ti = getLastTeleinfoFromDataBase()
   return ti

#-------------------------------------------------------------
# La page principale. WARNING : a virer, a terme
#-------------------------------------------------------------
@app.route("/")
def accueil():
   
   # Pour le moment la premiere page ne contient rien !
   templateData = {
      'version' : teleinfoVersion,
      'themeActuel' : themeActuel,

      'class_acc': 'active',
      'class_ins': 'inactive',
      'class_jou': 'inactive',
      'class_con': 'inactive',
   }
   return render_template('main.html', **templateData)

#-------------------------------------------------------------
# Une page de configuration
#-------------------------------------------------------------
@app.route("/configuration")
def configuration():

   templateData = {
      'version' : teleinfoVersion,
      'themeActuel' : themeActuel,

      'class_acc': 'inactive',
      'class_ins': 'inactive',
      'class_jou': 'inactive',
      'class_con': 'active',
   }
   return render_template('configuration.html', **templateData)

   
#--------------------------------------------------------
# La route suivante permet d'acceder a toutes les valeurs
# de la derniere trame lue. clef est le nom du label de
# la trame. La page fournie contient simplement la valeur
# sans fioriture
#--------------------------------------------------------
@app.route("/teleinfo/<clef>")
def lireClef(clef):
   ti = webGetLastTeleinfo()

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
   ti = webGetLastTeleinfo()

   if ('web' in debugFlags) :
      logging.info("[lireClefJSON] clef = "+clef+" valeur = "+str(ti[clef]))

   return Response(json.dumps(int(ti[clef])),mimetype='application/json')

#--------------------------------------------------------
#   Page d'affichage des valeurs instantanees
#--------------------------------------------------------
@app.route("/instantane")
def instantane():
   ti = webGetLastTeleinfo()

   templateData = {
      'version' : teleinfoVersion,
      'themeActuel' : themeActuel,
      'class_acc': 'inactive',
      'class_ins': 'active',
      'class_jou': 'inactive',
      'class_con': 'inactive',

      'prixhpjb': tarifs['hpjb'],
      'prixhcjb': tarifs['hcjb'],
      'prixhpjw': tarifs['hpjw'],
      'prixhcjw': tarifs['hcjw'],
      'prixhpjr': tarifs['hpjr'],
      'prixhcjr': tarifs['hcjr'],

      'bbrhpjb' : ti['bbrhpjb'],
      'bbrhpjw' : ti['bbrhpjw'],
      'bbrhpjr' : ti['bbrhpjr'],
      'bbrhcjb' : ti['bbrhcjb'],
      'bbrhcjw' : ti['bbrhcjw'],
      'bbrhcjr' : ti['bbrhcjr'],
      'demain'  : ti['demain'],
      'isousc' : ti['isousc'],
      'ptec' : ti['ptec'],
      'pmax' : str(230*ti['imax']),
      'time' : ti['time']
   }

   return render_template('instantane.html', **templateData)

#--------------------------------------------------------
#   La consommation sur une journee. WARNING : obsolete
# aller voir en dessous
#--------------------------------------------------------
@app.route("/consojournaliere/<when>")
def consojournaliere(when) :
   valeurs = {
      'bbrhpjb' : {'nom' : 'Pl. bleu', 'conso' : [] },
      'bbrhcjb' : {'nom' : 'Cr. bleu', 'conso' : [] },
      'bbrhpjw' : {'nom' : 'Pl. blanc', 'conso' : [] },
      'bbrhcjw' : {'nom' : 'Cr. blanc', 'conso' : [] },
      'bbrhpjr' : {'nom' : 'Pl. rouge', 'conso' : [] },
      'bbrhcjr' : {'nom' : 'Cr. rouge', 'conso' : [] }
   } 

   # Definition des creneaux horaires pour l'axe des X
   creneaux = []

   # On fait des requetes sur les dernieres 24h. Une requete
   # par creneau de 1h
   if (when == 'last') :
      debut = datetime.datetime.now() - datetime.timedelta(days = 1)
      title = 'Consommation sur les dernieres 24 heures'
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
         pui = puissanceCumulee(debut.date(), debut.time(), fin.date(), fin.time())
         creneaux.append(debut.strftime("%H:%M"))
         if ('web' in debugFlags) :
            logging.info("Entre " + debut.strftime("%x, %X") + " et " + fin.strftime("%x, %X") + " : ")
            logging.info(str(pui['bbrhpjb'])+"/"+str(pui['bbrhcjb'])+"/"+str(pui['bbrhpjw'])+"/"+str(pui['bbrhcjw'])+"/"+str(pui['bbrhpjr'])+"/"+str(pui['bbrhcjr']))
         valeurs['bbrhpjb']['conso'].append(str(pui['bbrhpjb']))
         valeurs['bbrhcjb']['conso'].append(str(pui['bbrhcjb']))
         valeurs['bbrhpjw']['conso'].append(str(pui['bbrhpjw']))
         valeurs['bbrhcjw']['conso'].append(str(pui['bbrhcjw']))
         valeurs['bbrhpjr']['conso'].append(str(pui['bbrhpjr']))
         valeurs['bbrhcjr']['conso'].append(str(pui['bbrhcjr']))
      else :
         valeurs['bbrhpjb']['conso'].append(0)
         valeurs['bbrhcjb']['conso'].append(0)
         valeurs['bbrhpjw']['conso'].append(0)
         valeurs['bbrhcjw']['conso'].append(0)
         valeurs['bbrhpjr']['conso'].append(0)
         valeurs['bbrhcjr']['conso'].append(0)
      debut = fin

   templateData = {
      'version' : teleinfoVersion,
      'themeActuel' : themeActuel,
      'class_acc': 'inactive',
      'class_ins': 'inactive',
      'class_jou': 'active',
      'class_con': 'inactive',

      'creneaux' : creneaux,
      'title'    : title,
      'valeurs'  : valeurs
   }
   return render_template('consojournaliere.html', **templateData)
   
#--------------------------------------------------------
#   La consommation sur une journee, nouvelle version !
# L'idee c'est que les choses affichables sont dans la
# variable "series" qui est mise a jour chaque fois que
# necessaire.
#--------------------------------------------------------
@app.route("/quotidien")
def quotidien() :
   templateData = {
      'version' : teleinfoVersion,
      'themeActuel' : themeActuel,
      'class_acc': 'inactive',
      'class_ins': 'inactive',
      'class_jou': 'inactive',
      'class_quo': 'active',
      'class_con': 'inactive',

      'creneaux' : creneaux,
      'title'    : title,
      'series'   : series
   }
   return render_template('quotidien.html', **templateData)

#=============================================================
# C'est parti mon kiki ...
#=============================================================

#-------------------------------------------------------------
# On va chercher la configuration dans les fichiers suivants et dans
# cet ordre
#   /etc/teleinfo.cfg
#   ${HOME}/.teleinfo.cfg
# L'idee est d'avoir une configuration generale dans le premier fichier
# qui sera notemment utiliseepar le serveur operationnel, et une
# configuration specifique a chque utilisateur qui permet de lancer
# des versions de debogage.
#-------------------------------------------------------------
config = ConfigParser.ConfigParser()

config.read(['/etc/teleinfo.cfg', os.path.expanduser('~/.teleinfo.cfg')])

# Lecture des parametres de configuration
#  La configuration generale
populateDataBase = config.getboolean('general', 'populateDataBase')
readFrames = config.getboolean('general', 'readFrames')
runWebServer = config.getboolean('general', 'runWebServer')

#  La base de donnees
mySQLServer = config.get('database', 'mySQLServer')
mySQLUserName  = config.get('database', 'mySQLUserName')
mySQLPassWord = config.get('database', 'mySQLPassWord')
mySQLDataBase = config.get('database', 'mySQLDataBase')
mySQLTable = config.get('database', 'mySQLTable')
queueBacklog = config.getint('database', 'backlog')
dbFailedDelay = config.getint('database', 'dbFailedDelay')

# La source de donnes
devicePath = config.get('source', 'devicePath')

#  Le serveur web
webPort = config.getint('web', 'port')
debugFlask = config.getboolean('web', 'debugFlask')

# Le contrat EDF
tarifs = {}
tarifs['hcjb'] = config.getfloat('contrat', 'tarifHCJB')
tarifs['hpjb'] = config.getfloat('contrat', 'tarifHPJB')
tarifs['hcjw'] = config.getfloat('contrat', 'tarifHCJW')
tarifs['hpjw'] = config.getfloat('contrat', 'tarifHPJW')
tarifs['hcjr'] = config.getfloat('contrat', 'tarifHCJR')
tarifs['hpjr'] = config.getfloat('contrat', 'tarifHPJR')

# Le debogage
debugFlags = config.get('debug', 'debugFlags')
logConsole = config.getboolean('debug', 'logConsole')
logFile = config.get('debug', 'logFile')
nbFrameMsgLog = config.getint('debug', 'nbFrameMsgLog')

#-------------------------------------------------------------
# Gestion des parametres
#-------------------------------------------------------------
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
   populateDataBase = False

if (args.no_web) :
   runWebServer = False

if (args.no_serial) :
   readFrames = False

if (args.log_console) :
   logConsole = True

#-------------------------------------------------------------

# Pour terminer (par ^C)
signal.signal(signal.SIGINT, signal_handler)

# Pour sigterm utilise par start-stop-daemon
signal.signal(signal.SIGTERM, signal_handler)

# Configuration du systeme de log
if (logConsole) :
   logging.basicConfig(format='%(asctime)s - %(levelname)s:%(message)s',
                       level=logging.DEBUG)
else :
   logging.basicConfig(filename=logFile,
                       format='%(asctime)s - %(levelname)s:%(message)s',
                       level=logging.DEBUG)

logging.info("*************************************")
logging.info("*************************************")
logging.info("*** Teleinfo version " + teleinfoVersion + " running ***")
logging.info("*************************************")
logging.info("*************************************")

#=========================================================
# Initialisation du port serie
#=========================================================
if (readFrames) :
   if (debugFlask) :
      logging.info("debugFlask incompatible avec readFrames, on le desactive !")
      debugFlask = False
   fd=initSerialPort()
else :
   if (populateDataBase) :
      logging.info("populateDataBase impossible si readFrames == False, on desactive !")
      populateDataBase = False

#=========================================================
# Structures d'echange des donnees
#=========================================================

# On va inserer les trames dans une file (thread safe !)
# On les traitera de facon asynchrone
frameQueue = Queue.Queue();

# Les teleinfo creees sont inserees dans une file
# afin d'etre ensuite sauvegardees (par exemple dans
# une base de donnees)
teleinfoQueue = Queue.Queue(queueBacklog);

# Pour proteger le teleinfo
teleinfoLock = threading.Lock();

#=========================================================
# Lancement des threads
#=========================================================

# Le thread de lecture et le thread de conversion trame -> teleinfo
if (readFrames) :
   threadLecture = threading.Thread(target=teleinfoReadFrame, args=(fd, frameQueue,))
   threadLecture.start()
   threadConversion = threading.Thread(target=frameQueueProcess, args=(frameQueue, teleinfoQueue))
   threadConversion.start()

# Le thread de sauvegarde
if (populateDataBase) :
   threadSauvegarde = threading.Thread(target=saveTeleinfo, args=(teleinfoQueue, ))
   threadSauvegarde.start()

# Le thread de recuperation des donnees
if (runWebServer and not readFrames) :
   threadGetData = threading.Thread(target=getData)

# On demarre le serveur web
if __name__ == "__main__":
   if (runWebServer) :
      logging.info("Lancement du serveur web")
      # Attention, pas de debug en multithreads
      app.run(host='0.0.0.0', port=8081, debug=debugFlask)
   # Sinon, on attend la fin des threads
   else :
      logging.info("Pas de serveur web")
      if (populateDataBase) :
         threadSauvegarde.join()
   # Sinon on ne fait rien !
