import tornado.ioloop
import tornado.web
import requests
import json
from models import Base, Words, Links
from Crypto import Random
from Crypto.PublicKey import RSA
import base64
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from settings import *
from tornado.log import enable_pretty_logging

# connect to mysql database and create session
connection_string = 'mysql+pymysql://{}:{}@{}/{}' \
    .format(DATABASE_SETTINGS['user'],DATABASE_SETTINGS['password'],DATABASE_SETTINGS['host'],DATABASE_SETTINGS['database'])
engine = create_engine(connection_string, pool_recycle=3600)
connection = engine.connect()
Base.metadata.create_all(engine)

def generate_or_read_keys():
    try:
        # check if public and private key exists
        publickey_file = open(PROJECT_PATH + "/publickey", "rb")
        privatekey_file = open(PROJECT_PATH + "/privatekey", "rb")
        publickey_txt = publickey_file.read()
        privatekey_txt = privatekey_file.read()
        publickey = RSA.importKey(publickey_txt)
        privatekey = RSA.importKey(privatekey_txt)

        publickey_file.close()
        privatekey_file.close()
    except:
        # RSA modulus length must be a multiple of 256 and >= 1024
        modulus_length = 256*4 # use larger value in production
        privatekey = RSA.generate(modulus_length, Random.new().read)
        publickey = privatekey.publickey()
        # export keys
        privatekey_export = privatekey.exportKey()
        publickey_export = publickey.exportKey()
        publickey_file = open(PROJECT_PATH + "/publickey","wb")
        publickey_file.write(publickey_export)
        publickey_file.close()
        privatekey_file = open(PROJECT_PATH + "/privatekey","wb")
        privatekey_file.write(privatekey_export)
        privatekey_file.close()

    return publickey, privatekey

def encrypt_message(a_message , publickey):
    encrypted_msg = publickey.encrypt(a_message.encode('utf-8'), 32)[0]
    encoded_encrypted_msg = base64.b64encode(encrypted_msg) # base64 encoded strings are database friendly
    return encoded_encrypted_msg

def decrypt_message(encoded_encrypted_msg, privatekey):
    decoded_encrypted_msg = base64.b64decode(encoded_encrypted_msg)
    decoded_decrypted_msg = privatekey.decrypt(decoded_encrypted_msg)
    return decoded_decrypted_msg

def get_sentiment(words=None):
    #gets the sentiment from wit.io and gives a positive or negative point according to wordcount
    #at the end returns a positive, negative or neutral result
    if words is None:
        return None
    # limiting wors to top 50 as it takes sometime to run
    number_of_words = len(words)
    limitwords = 50 if number_of_words >= 50 else number_of_words
    words = words[0:limitwords]
    negative = 0
    positive = 0
    headers = {'Authorization': 'Bearer HXN77N6WCDX7DHRRSDGTCCDVHDFSLCL6'}
    print("Starting sentiment analysis")
    for w in words:
        resturl = "https://api.wit.ai/message?v=20180519&q=" + w[0]
        response = requests.get(resturl, headers=headers)
        text_sentiment = response.text
        json_sentiment = json.loads(text_sentiment)
        print(json_sentiment)
        try:
            sentiment = json_sentiment['entities']['sentiment'][0]['value']
            if sentiment=='positive':
                positive+=1*w[1]
            elif sentiment=='negative':
                negative+=1*w[1]
        except:
            sentiment = 'neutral'
        if sentiment != 'neutral':
            print("---- Positive: {} - Negative {} ----".format(positive,negative))
    # Assumes positive for equal results
    if positive>=negative:
        sentiment="Positive"
    else:
        sentiment="Negative"
    return  sentiment


def cleanup_text_count_sort(text=None):
    # cleanups the text
    from operator import itemgetter
    import nltk
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize
    nltk.download('stopwords')
    nltk.download('punkt')
    stop_words = set(stopwords.words('english'))

    if text is None:
        return None
    # remove line breaks and tabs
    text = text.replace("\n"," ").replace("\t"," ")
    # remove repeating spaces and make all words lowercase
    text = " ".join(text.split())
    text = text.lower()
    word_tokens = word_tokenize(text)
    # clear unnecessary words
    filtered_words = [w for w in word_tokens if not w in stop_words]
    # remove text that are one char and only digits
    filtered_words2 = [w for w in filtered_words if len(w)>1 and not w.isdigit()]
    filtered_words = filtered_words2
    # remove 2 char text that are not only letters
    filtered_words2 = [w for w in filtered_words if not (len(w) == 2 and not w.isalpha())]
    filtered_words = filtered_words2
    wordcount = {}
    for word in filtered_words:
        if word not in wordcount:
            wordcount[word] = 1
        else:
            wordcount[word] += 1
    wordcount = wordcount.items()
    wordcount_sorted = sorted(wordcount, key=itemgetter(1), reverse=True)
    return wordcount_sorted


def get_salted_hash(word=None):
    # gives salted hash of the word
    import hashlib, uuid
    if word is None:
        return None
    #salt = uuid.uuid4().hex
    salt = SALT
    hashed_word = hashlib.sha512(word.encode('utf-8') + salt.encode('utf-8')).hexdigest()
    return hashed_word

def add_words_to_db(words=None):
    if words is None:
        return None
    Session = sessionmaker(bind=engine)
    session = Session()
    # get keys for encryption
    publickey, privatekey = generate_or_read_keys()
    for w in words:
        word_id = get_salted_hash(word=w[0])
        word_count = w[1]
        # check if record exists
        record = session.query(Words).filter_by(word_id=word_id).first()
        if record:
            # if exists increase count
            record.word_count += word_count
            session.commit()
            pass
        else:
            # if does not exist create record
            word_text = encrypt_message(a_message=w[0],publickey=publickey)
            cc_word = Words(word_id=word_id,word_text=word_text,word_count=word_count)
            session.add(cc_word)
    session.commit()
    session.close()

def add_url_to_db(url=None,sentiment=None):
    if url is None or sentiment is None:
        return None
    Session = sessionmaker(bind=engine)
    session = Session()
    url_id = get_salted_hash(url)
    url_text = url
    record = session.query(Links).filter_by(url_id=url_id).first()
    if record:
        record.sentiment = sentiment
    else:
        cc_url = Links(url_id=url_id,url_text=url_text,sentiment=sentiment)
        session.add(cc_url)
    session.commit()
    session.close()

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        form_error=""
        words=""
        self.render("templates/index.html", title=TITLE,form_error=form_error,words=words)

    def post(self):
        from bs4 import BeautifulSoup
        from random import shuffle, random

        form_error = ""
        words= ""
        # Get url input from form
        url  = self.get_argument("url", "")
        try:
            response = requests.get(url)
        except:
            # If url not valid display error
            form_error = "Please provide a valid URL"
            self.render("templates/index.html", title=TITLE, form_error=form_error,words=words)
            return
        # get html text
        html = response.text
        soup = BeautifulSoup(html, "html5lib")
        # kill all script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text()
        wordcount_sorted = cleanup_text_count_sort(text=text)
        number_of_words = len(wordcount_sorted)
        # limit words to 100 if number of words is more than 100
        limitwords = 100 if number_of_words>=100 else number_of_words
        top_100_words = wordcount_sorted[0:limitwords]
        # add words to database
        add_words_to_db(words=top_100_words)
        # shuffle words for word cloud
        shuffled_100_words = top_100_words
        shuffle(shuffled_100_words, random)
        # use count for font size, to show fonts bigger multiply count by 3l
        wordlist = [(w[0],w[1]*3) for w in shuffled_100_words]
        # make the sentiment analyis according to top 100 words
        sentiment = get_sentiment(words=top_100_words)
        add_url_to_db(url=url,sentiment=sentiment)
        self.render("templates/index.html", title=TITLE, url=url,form_error=form_error,words=wordlist)

class AdminPage(tornado.web.RequestHandler):

    def get(self):
        Session = sessionmaker(bind=engine)
        session = Session()
        from sqlalchemy import desc
        publickey, privatekey = generate_or_read_keys()
        results = []
        for w in session.query(Words).order_by(desc(Words.word_count)):
            result = {}
            result['word_text'] = decrypt_message(encoded_encrypted_msg=w.word_text,privatekey=privatekey)
            result['word_count'] = w.word_count
            results.append(result)

        links = session.query(Links).all()
        self.render("templates/admin.html", title="Admin Page",words=results,links=links)

def make_app():
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/admin", AdminPage),
        (r"/media/(.*)", tornado.web.StaticFileHandler, {'path': "./media"}),
    ],**APP_SETTINGS)


if __name__ == "__main__":
    app = make_app()
    app.listen(8888)
    tornado.autoreload.start()
    tornado.autoreload.watch(PROJECT_PATH + "/templates/base.html")
    tornado.autoreload.watch(PROJECT_PATH + "/main.py")
    enable_pretty_logging()
    tornado.ioloop.IOLoop.current().start()
    
