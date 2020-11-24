# doko3000

Simple Doppelkopf deck simulation via web browser.

## Overview

The 2020 coronavirus pandemic spring lockdown forced us to move our Doppelkopf gatherings from real world to online.
Doko3000 helps to keep the ongoing league competition going.

It just provides a **virtual table** with **virtual cards**. Players play like in the real world, preferably talking to each
other via video conference in a parallel window.
To keep as much normality during the pandemic, doko3000 is intended to be **as digital as necessary, as analog as possible**.
This is why **no rules** are included, because there are so many and players should apply them like sitting at a real table.
For the same reason there are **no scoreboards** or statistics - it will even feel more familiar if somebody of the group
notes the score as before.

Ingame language at the moment is only german due to Doppelkopf being a mostly german phenomenon. Might change in the future.

## Screenshots

Player sees cards in its hand and the ones on the table. The display at the top shows all 4 players of the current round:

![Playing doko3000](doc/doko3000-play.png)

A big green button appears when there is a trick to claim:

![Claiming a trick](doc/doko3000-claim_trick.png)

After the round was finished the achieved score of the players is shown:

![Finished round](doc/doko3000-round_finished.png)

The table settings allow to arrange players and enable some options:

![Table setup](doc/doko3000-table_setup.png)


## Installation

Doko3000 is a [Python](https://python.org) web application mostly based on:

 - [Flask](https://flask.palletsprojects.com)
 - [Flask-SocketIO](https://flask-socketio.readthedocs.io)
 - [CouchDB](https://couchdb.apache.org/)
 - [SVG-Cards](http://svg-cards.sourceforge.net/)
 - [Dragula](https://bevacqua.github.io/dragula/)
 - [Bootstrap](https://getbootstrap.com)
 - [jQuery](https://jquery.com)
 
As **server** anything capable of running Python might work, but best experiences were made with **containers** on Linux.
 
As **client** any current browser will do, as long as it can make use of WebSocket, which is
necessary for the game communication.
 
### Getting doko3000
 
At the moment it is only available from Github:
 
    git clone https://github.com/HenriWahl/doko3000.git
 
All further steps are based on the `doko3000` directory:
 
    cd doko3000
     
### docker-compose.yml
  
In [/docker](./docker) there are 3 example **docker-compose** configuration files. Just copy one of them to the root 
directory you're in:
  
    cp docker/docker-compose.yml .
  
If you plan to use HTTPS better use the *docker-compose-https.yml* file, which will need some customization regarding
the certificate and key file:
  
    cp docker/docker-compose-https.yml docker-compose.yml
    
The third file *docker-compose-https-letsencrypt.yml* can be used for Let's Encrypt setups and is based on 
[Nginx and Let’s Encrypt with Docker in Less Than 5 Minutes](https://medium.com/@pentacent/nginx-and-lets-encrypt-with-docker-in-less-than-5-minutes-b4b8a60d3a71) -
maybe there is a more elegant way but it works fine here. This docker-compose config surely has to be customized by you.
    
### Environment file
 
The file [docker/default.env](./docker/default.env) can be copied to **.env**, wherever **docker-compose** is intended to be run.
Inside the environment file you could set optional variables - if not, doko3000 is able to run with defaults too:
 
- **HOST** - name of the server host to be used at least as *cors_allowed_origins* in flask
- **SECRET_KEY** - secret key for flask sessions
- **COUCHDB_USER**  - CouchDB user used by doko3000 and couchdb containers
- **COUCHDB_PASSWORD** - CouchDB password used by doko3000 and couchdb containers

 
    cp docker/default.env .env
 
If any of the configuration variables is important to you just change them there.
 
### Running the server
 
If everything is configured you can start the server with
 
    docker-compose up -d
 
If you run it on your local machine, point your favorite browser to http://localhost and you will find the login page:
 
![doko3000 login](doc/doko3000-login.png)
 
The **default user** is `admin` with the password `admin` and admin rights. It can create other players and should
get a new password soon.
 
*To be continued soon*