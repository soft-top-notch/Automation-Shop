import requests

class UserInfo:
    def __init__(self,
                 first_name,
                 last_name,
                 home,
                 street,
                 zip,
                 city,
                 state,
                 country,
                 phone,
                 email,
                 password,
                 company
                 ):
        self.first_name = first_name
        self.last_name = last_name
        self.home = home
        self.street = street
        self.zip = zip
        self.city = city
        self.state = state
        self.country = country
        self.phone = phone
        self.email = email
        self.password = password
        self.company = company

    def get_json_userinfo(self):
        return {
            "first name": self.first_name,
            "last name": self.last_name,
            "full name": self.first_name + " " + self.last_name,
            "country": self.country,
            "state": self.state,
            "home": self.home,
            "street": self.street,
            "zip": self.zip,
            "city": self.city,
            "phone": self.phone,
            "email": self.email,
            "password": self.password,
            "company": self.company,
        }


class PaymentInfo:
    def __init__(self,
                 card_number,
                 card_name,
                 card_type,
                 expire_date_year,
                 expire_date_month,
                 cvc,
                 zip
                 ):
        self.card_number = card_number
        self.card_name = card_name
        self.card_type = card_type
        self.expire_date_year = expire_date_year
        self.expire_date_month = expire_date_month
        self.cvc = cvc
        self.zip = zip

    def get_json_paymentinfo(self):
        return {
            "number": self.card_number,
            "name": self.card_name,
            "type": self.card_type,
            "expdate": self.expire_date_month + self.expire_date_year,
            "birthdate": self.expire_date_month + "0119" + self.expire_date_year,
            "cvc": self.cvc,
            "zip": self.zip
        }


def get_user_data(url = 'http://127.0.0.1:8989/json'):
    r = requests.post(url)
    data = r.json()

    address = data['Street:'].split(' ')
    home = address[0]
    street = " ".join(address[1:])
    password = "Payment123"
    company = "ULTC"

    user_info = UserInfo(
        data['First Name:'],
        data['Last Name:'],
        home,
        street,
        data['Zip code:'],
        data['City:'],
        data['State:'],
        data['Country'],
        data['Phone:'],
        data['E-mail:'],
        password,
        company
    )

    month, year = data['CC exp. date:'].split('/')
    payment_info = PaymentInfo(
        data['CC Number:'],
        user_info.first_name + " " + user_info.last_name,
        data['CC provider:'],
        year,
        month,
        data['CC CVV'],
        data['Zip code:']
    )

    return user_info, payment_info
