*****************************************************************************
Configuration port série: 1 start, 8 bit, 1 stop (vitesse 9600 bauds)
*****************************************************************************
La trame est composée de 5 caractères (minuscule ou majuscule) pouvant etre envoyés en ASCII ou en Hexadécimal

****************
Code ascii
****************
                          
Start of frame: RLY
N° channel: 0 à 8
CMD: 0 ou 1

Exemple de trame:

RLY11 // commute le relais 1 en position travail
RLY10 // commute le relais 1 en position repos
RLY21 // commute le relais 2 en position travail
...........................................................................
RLY80 commute le relais 8 en position repos

En cas de mauvaise commande la carte renvoi un retour chariot et le caractère ?

****************
Code hexa
****************
Start of frame:  0x52 0x4C 0x59 ou 0x72 0x6C 0x79
N° channel: 0x31 à 0x38
Cmd: 0x30 ou 0x31


Exemple de trame:

0x52 0x4C 0x59 0x31 0x31 // commute le relais 1 en position travail
0x52 0x4C 0x59 0x31 0x30 // commute le relais 1 en position repos
0x52 0x4C 0x59 0x32 0x31 // commute le relais 2 en position travail
...........................................................................
0x52 0x4C 0x59 0x38 0x30 commute le relais 8 en position repos

Pour tout autre caractère ou chaines de caractères la carte renvoi le code suivant:
0x0D 0x3F
*******************************************************************************
Modification du :04/09/2009
*******************************************************************************

Rajout du mode mémoire: la carte garde la dernière configuration en mémoire en cas de coupure d'alimentation.


****************
Code ascii 
****************
M0 // Mode mémore désactivé
M1 // Mode mémoire activé

****************
Code hexa
****************
0x4D 0x30 // Mode mémore désactivé
0x4D 0x31 // Mode mémoire activé
*******************************************************************************

Rajout d'une commande pour connaitre l'état des relais.


****************
Code ascii 
****************
?RLY // Renvoi l'état logique des 8 relais sous la forme >00000000   (le caractère le plus  à droite correspond au relais 8)

****************
Code hexa
****************
0X3F 0x52 0x4C 0x59 // Renvoi l'état logique des 8 relais sous la forme >00000000   (le caractère le plus  à droite correspond au relais 8)


******************************************************************************

