# HFeasy pour Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Validation](https://github.com/pismache/ha-hfeasy/actions/workflows/validate.yml/badge.svg)](https://github.com/pismache/ha-hfeasy/actions/workflows/validate.yml)

Pilotage **local** des prises connectées flashées avec le firmware
[HFeasy](https://github.com/ljalves/hfeasy) (modules HF-LPB100 / HF-LPB130),
sans cloud ni MQTT : Home Assistant interroge directement la page `/state` de la prise.

Remplace la configuration manuelle habituelle (capteur `rest` + deux `rest_command` + un `switch` template)
par **une seule entité interrupteur**, configurable depuis l'interface.

## Fonctionnalités

- Un appareil par prise, avec un interrupteur (classe « prise ») ;
- état mis à jour immédiatement après chaque commande, puis relu toutes les 30 s (réglable de 5 à 3600 s) ;
- la prise passe en « indisponible » si elle ne répond plus, et revient d'elle-même ;
- authentification HTTP facultative (si la page web de la prise est protégée) ;
- changement d'adresse IP sans perdre l'entité ni l'historique (menu ⋮ → **Reconfigurer**).

## Installation

1. HACS → ⋮ → **Dépôts personnalisés** → `https://github.com/pismache/ha-hfeasy`, catégorie **Intégration**.
2. Installer **HFeasy**, puis redémarrer Home Assistant.
3. **Paramètres → Appareils et services → Ajouter une intégration → HFeasy**.
4. Saisir l'adresse IP de la prise, le port (8080 par défaut) et un nom.
   Identifiant et mot de passe ne sont à remplir que si la page de la prise en demande.

Une prise = une entrée : recommencez l'étape 3 pour chaque prise.

## Migration depuis la configuration REST

Une fois l'intégration ajoutée et l'interrupteur fonctionnel, supprimez de votre configuration :

- le capteur `binary_sensor` `rest` pointant sur `http://<ip>:8080/state` ;
- les `rest_command` d'allumage et d'extinction (`/state?sw=1` et `/state?sw=0`) ;
- le `switch` template qui les reliait.

Redémarrez, puis remplacez l'ancienne entité par la nouvelle dans vos tableaux de bord et automatisations.

## Ce que fait l'intégration côté prise

| Action    | Requête                     |
|-----------|-----------------------------|
| Lire      | `GET /state`                |
| Allumer   | `GET /state?sw=1`           |
| Éteindre  | `GET /state?sw=0`           |

Réponse attendue : `{"set":"none","relay_status":"1"}`.

## Licence

MIT. Projet indépendant, non affilié au projet HFeasy.
