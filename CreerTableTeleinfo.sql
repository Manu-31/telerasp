/*
   Creation d'une base domotique avec une table pour les
  teleinfo. Ici la table permet de gérer des informations
  sur un contrat de type Tempo (bleu blanc rouge). En 
  commentaire des choses pour d'autres contrats (sans
  garantie)
*/
CREATE DATABASE Domotique ;
USE Domotique ;
CREATE TABLE IF NOT EXISTS `teleinfo` (
    `date` DATE NOT NULL DEFAULT '0000-00-00',  # Date de la trame
    `time` TIME NOT NULL DEFAULT '00:00:00',    # Heure de la trame

    `adco` VARCHAR(12) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL, # Adresse du compteur
    `optarif` VARCHAR(4) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL, # Le contrat, est-ce bien utile ?
    `isousc` tinyint(2) NOT NULL DEFAULT '0', # intensité souscrite

# Pour un contrat de base
#    `base` BIGINT(9) NOT NULL DEFAULT '0',

# Pour un contrat HP/HC
#    `hchp` BIGINT(9) NOT NULL DEFAULT '0',
#    `hchc` BIGINT(9) NOT NULL DEFAULT '0',

# Pour un contrat EJP
#    `ejphn` BIGINT(9) NOT NULL DEFAULT '0',
#    `ejphpm` BIGINT(9) NOT NULL DEFAULT '0',

# Tarif Tempo uniquement
    `bbrhcjb` BIGINT(9) NOT NULL DEFAULT '0', # Heures creuse jours pleins
    `bbrhpjb` BIGINT(9) NOT NULL DEFAULT '0', # 
    `bbrhcjw` BIGINT(9) NOT NULL DEFAULT '0', # 
    `bbrhpjw` BIGINT(9) NOT NULL DEFAULT '0', # 
    `bbrhcjr` BIGINT(9) NOT NULL DEFAULT '0', # 
    `bbrhpjr` BIGINT(9) NOT NULL DEFAULT '0', # 

# Tarif EJP uniquement
#    `pejp` tinyint(2) NOT NULL DEFAULT '0', # Préavis début EJP

    `ptec` VARCHAR(2) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,

# Tarif Tempo uniquement
    `demain` VARCHAR(4) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL, # Couleur de demain

    `iinst` tinyint(3) NOT NULL DEFAULT '0', # Intensité instantané
    `imax` tinyint(3) NOT NULL DEFAULT '0', # Intensité maximale

    `papp` INT(5) NOT NULL DEFAULT '0', # Puissance apprente
    `hhphc` VARCHAR(1) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
    `motdetat` VARCHAR(6) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL

) ENGINE=MyISAM DEFAULT CHARSET=latin1;
