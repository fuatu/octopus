import os

# database settings
# for docker keep hostname db or change the database hostname in docker.compose.yml accordingly
DATABASE_SETTINGS = {
    'database': 'octopus',
    'host': 'db',
    'user': 'octotest',
    'password': 'Q1x2v4c5',
}

TITLE = "Sentiment Analysis Example"
SALT = "mysalt"

APP_SETTINGS = {
    "Debug": True,
    "autoreload":True,
}

PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))