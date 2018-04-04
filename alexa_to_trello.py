from bs4 import BeautifulSoup
import configparser
import json
import requests
import sys
import urllib
import getopt
from time import sleep


# Sets up the interface to Amazon Alexa

class AmazonManager():

    def __init__(self, email, password):

        self.email = email
        self.password = password
        self.session = requests.Session()

        self.default_headers = {
            'User-Agent': 'Mozilla/5.0 (X11; U; Linux x86_64; en-US; rv:1.9.2.13) ' \
                          + 'Gecko/20101206 Ubuntu/10.10 (maverick) Firefox/3.6.13',
            'Charset': 'utf-8',
            'Origin': 'http://alexa.amazon.com',
            'Referer': 'http://alexa.amazon.com/spa/index.html',
        }

        self.session.headers.update(self.default_headers)
        self.login()

    def find_csrf_cookie(self):
        for cookie in self.session.cookies:
            if cookie.name == "csrf":
                return cookie.value
        return None

    def delete_items(self, items):

        # This PUT request needs special headers
        headers = {
            'Content-type': 'application/json',
            'csrf': self.find_csrf_cookie(),
            'Accept': 'application/json, text/javascript, */*; q=0.01',
        }

        # Loop through the items and delete each one
        for item in items:
            id = urllib.parse.quote_plus(item['itemId'])
            item['deleted'] = True
            url = 'https://api.amazonalexa.com/v2/householdlists/shopping_list_list_id/active'
            delete_request = self.session.put(url, data=json.dumps(item), headers=headers)

            if not delete_request.status_code == 200:
                print("Error deleting item")

    def fetch_items(self):

        # Request the shopping list API
        url = 'https://api.amazonalexa.com/v2/householdlists/shopping_list_list_id/active'
        shopping_request = self.session.get(url)

        data = shopping_request.json()

        # Find all the items
        items = []
        if 'values' in data:
            for value in data['values']:
                items.append(value)

        # Return our list of item objects
        return items

    def logout(self):
        self.session.headers.update({'Referer': 'http://alexa.amazon.com/spa/index.html'})
        url = 'https://alexa.amazon.com/logout'
        self.get(url)

    def login(self):

        # Request the login page
        login_url = 'https://alexa.amazon.com'
        login_request = self.session.get(login_url)

        # Turn the login page into a soup object
        login_soup = BeautifulSoup(login_request.text, 'html.parser')

        # Find the <form> tag and the action from the login page
        form_el = login_soup.find('form')
        action_attr = form_el.get('action')

        # Set up the parameters we will pass to the sign-in
        parameters = {
            'email': self.email,
            'password': self.password,
            'create': 0,
        }

        # Find all the hidden form elements and stick them in the params
        for hidden_el in form_el.findAll(type="hidden"):
            parameters[hidden_el.get('name')] = hidden_el.get('value') # I have a feeling this is wrong

        # Update the session with the new referer
        self.session.headers.update({'Referer': login_url})

        # Post to the login page
        login_request = self.session.post(action_attr, data=parameters)

        # Make sure it was successful
        if login_request.status_code != 200:
            sys.exit("Error logging in! Got status %d" % login.status_code)

class TrelloManager():

    def __init__(self, app_key, secret, token):
        self.app_key = app_key
        self.secret = secret
        self.token = token

    def fetch_json(self, uri_path, http_method='GET', post_args=None, query_params=None):

        headers = {}
        data = json.dumps(post_args)

        if http_method in ("POST", "PUT", "DELETE"):
            headers['Content-Type'] = 'application/json; charset=utf-8'
            headers['Accept'] = 'application/json'

        # Need to fix this.
        # Structure of the URL is https://api.trello.com/1/boards/{boardID}?fields=name,url&key={YOUR-API-KEY}&token={AN-OAUTH-TOKEN}
        # But what about the listId?
        url = 'https://api.trello.com/1/%s' % uri_path
        print("url: " + url)

        # Perform the HTTP requests, if possible uses OAuth authentication
        response = requests.request(http_method, url, params=query_params, headers=headers, data=data)

        return response.json()

    # Eventually edit this to add to a checklist instead of a card. Is this possible?
    def create_card(self, name, idList, desc = None):
        json_obj = self.fetch_json('lists/' + idList + '/cards',
                                   http_method='POST',
                                   post_args={'name': name, 'idList': idList, 'desc': desc},
                                   query_params={'key': self.app_key, 'token': self.token}, )


def process_list(manager, trello, buy_list_id):
    # Get all the items on your shopping list
    items = manager.fetch_items()

    for item in items:
        name = item['text']
        print("creating card for " + name)
        trello.create_card(name, buy_list_id)


def main(argv):

    # process command line args
    single_run = False
    opts, args = getopt.getopt(argv, "s")
    for opt, arg in opts:
        if opt == "-s":
            single_run = True

    # Load the config info from the config.txt file
    config = configparser.ConfigParser()
    config.read("config.txt")

    # Make sure we have the items in the config.txt file
    try:
        email = config.get('Amazon', 'email')
        password = config.get('Amazon', 'password')
        app_key = config.get('Trello', 'app_key')
        secret = config.get('Trello', 'secret')
        token = config.get('Trello', 'token')
        buy_list_id = config.get('Trello', 'buy_list_id')
        poll_time_in_seconds = int(config.get('Schedule', 'poll_time_in_seconds'))

    except Exception:
        sys.exit("Invalid or missing config.txt file.")

    # Instantiate the Amazon and Trello wrappers
    manager = AmazonManager(email, password)
    trello = TrelloManager(app_key, secret, token)

    while True:
        process_list(manager, trello, buy_list_id)
        if single_run:
            break
        sleep(poll_time_in_seconds)
        print(".")

if __name__ == "__main__":
    main(sys.argv[1:])
