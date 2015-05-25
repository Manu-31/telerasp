# Un petit script pour generer une premiere version
# du fichier de config de teleinfo.py

import ConfigParser, os

config = ConfigParser.ConfigParser()

# When adding sections or items, add them in the reverse order of
# how you want them to be displayed in the actual file.
# In addition, please note that using RawConfigParser's and the raw
# mode of ConfigParser's respective set functions, you can assign
# non-string values to keys internally, but will receive an error
# when attempting to write to a file or when you get it in non-raw
# mode. SafeConfigParser does not allow such assignments to take place.
#config.add_section('web')
#config.set('web', 'port', '8081')

#config.add_section('database')
#config.set('database', 'mySQLServer', 'mani.manu-chaput.net')

# Writing our configuration file to 'example.cfg'
#with open('example.cfg', 'wb') as configfile:
#    config.write(configfile)

#config.read('example.cfg')

#=======================================================================
# On va chercher la configuration dans les fichiers suivants et dans
# cet ordre
#   /etc/teleinfo.cfg
#   ${HOME}/.teleinfo.cfg
# L'idee est d'avoir une configuration generale dans le premier fichier
# qui sera notemment utiliseepar le serveur operationnel, et une
# configuration specifique a chque utilisateur qui permet de lancer
# des versions de debogage.
#=======================================================================

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

print 'server   : ' + mySQLServer
print 'username : ' + mySQLUserName
print 'password : ' + mySQLPassWord
print 'database : ' + mySQLDataBase
print 'table    : ' + mySQLTable
print 'debugFlags : ' + debugFlags

