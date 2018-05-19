# Octopus Challange

## To install manually

- Create mysql database and give permissions

      $ mysql -u root -p
      > create database octopus;
      > GRANT ALL PRIVILEGES ON octopus.* TO 'octotest'@'localhost' IDENTIFIED BY 'Q1x2v4c5';

 - In project folder install requirements. It is suggested to use virtual environment

       $ pip3 install -r requirements.txt

- run the server

      $ python3 main.py

- access it from http://localhost:8888

