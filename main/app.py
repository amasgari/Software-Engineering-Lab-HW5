import base64
import datetime

import flask
# import form as form
from flask import Flask, render_template
from flask import jsonify
from flask import request
from flask import Flask, redirect, url_for

from flask_jwt_extended import create_access_token
from flask_jwt_extended import get_jwt_identity
from flask_jwt_extended import jwt_required
from flask_jwt_extended import JWTManager
import sqlalchemy as db
from sqlalchemy.orm import Session

import models
from PointingService import pointing
from event_model import Riding
from haversine import haversine
from models import Customer, Bike, Ride

from rq import Queue
from rq.job import Job

from sqlalchemy import Date, func
import requests

from worker import conn

Base = models.Base

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = "se-lab"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(minutes=5)
jwt = JWTManager(app)

q = Queue(connection=conn)

engine = db.create_engine('sqlite:///bike_sharing.sqlite')
# connection = engine.connect()
# metadata = db.MetaData()
Base.metadata.create_all(engine)

event_engine = db.create_engine('sqlite:///bike_sharing.sqlite')


def make_bikes():
    session = Session(engine)
    bike1 = Bike(status="available", loc_x=1, loc_y=4)
    bike2 = Bike(status="available", loc_x=3, loc_y=10)
    bike3 = Bike(status="available", loc_x=7, loc_y=6)
    session.add(bike1)
    session.add(bike2)
    session.add(bike3)
    session.commit()
    session.close()


@app.route("/", methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if request.form.get('Login') == 'login':
            return redirect(url_for('login_view'))
        elif request.form.get('Signup') == 'signup':
            return redirect(url_for('signup_view'))
        else:
            return "Error"
    elif request.method == 'GET':
        return render_template('index.html', form=request.form)

    return render_template("index.html")


@app.route('/login_view', methods=['GET', 'POST'])
def login_view():
    if request.method == 'GET':
        return render_template("login.html")
    else:
        username = request.form['username']
        password = request.form['password']
        loc_x = request.form['loc_x']
        loc_y = request.form['loc_y']
        dictToSend = {'username': username, "password": password, "loc_x": loc_x, "loc_y": loc_y}
        res = requests.post('http://localhost:5000/login', json=dictToSend)
        return res.text


@app.route('/signup_view', methods=['GET', 'POST'])
def signup_view():
    if request.method == 'GET':
        return render_template("login.html")
    else:
        username = request.form['username']
        password = request.form['password']
        loc_x = request.form['loc_x']
        loc_y = request.form['loc_y']
        dictToSend = {'username': username, "password": password, "loc_x": loc_x, "loc_y": loc_y}
        res = requests.post('http://localhost:5000//signup', json=dictToSend)
        return res.text


@app.route('/get_ride_view', methods=['GET', 'POST'])
def get_ride_view():
    if request.method == 'GET':
        return render_template("get_ride.html")
    else:
        access_token = request.form['access_token']
        bike_id = request.form['bike_id']
        dictToSend = {"bike_id": bike_id}
        headers = {
            'Authorization': "Bearer " + access_token
        }
        res = requests.get('http://localhost:5000//get_ride', json=dictToSend, headers=headers)
        return res.text


@app.route('/end_ride_view', methods=['GET', 'POST'])
def end_ride_view():
    if request.method == 'GET':
        return render_template("end_ride.html")
    else:
        access_token = request.form['access_token']
        ride_id = request.form['ride_id']
        loc_x = request.form['loc_x']
        loc_y = request.form['loc_y']

        dictToSend = {"access_token": access_token, "ride_id": ride_id, "loc_x": loc_x, "loc_y": loc_y}
        headers = {
            'Authorization': "Bearer " + access_token
        }
        res = requests.get('http://localhost:5000//end_ride', json=dictToSend, headers=headers)
        return res.text


@app.route('/update_user', methods=['POST'])
def update_user_view():
    point = request.json.get("point", None)
    user_id = request.json.get("user_id", None)
    session = Session(engine)
    user_obj = session.query(Customer).get(user_id)
    user_obj.total_points += point
    session.commit()
    session.close()
    return "done"


# --------------------------------------------------------------------------------
# Create a route to authenticate your users and return JWTs. The
# create_access_token() function is used to actually generate the JWT.
@app.route("/login", methods=["POST"])
def login():
    username = request.json.get("username", None)
    password = request.json.get("password", None)
    loc_x = request.json.get("loc_x", None)
    loc_y = request.json.get("loc_y", None)

    session = Session(engine)
    user_obj = session.query(Customer).filter_by(username=username).first()
    # user_obj = session.query(Customer).get({"username": username, "password": password})
    if user_obj is None:
        session.close()
        return jsonify({"Error": "Username is incorrect"}), 401
    if user_obj.password != password:
        session.close()
        return jsonify({"Error": "Password is incorrect"}), 401

    user_obj.loc_x = int(str(loc_x))
    user_obj.loc_y = int(str(loc_y))
    session.commit()
    access_token = create_access_token(identity=user_obj.id)
    session.close()
    return render_template("homepage.html", access_token=access_token)


@app.route("/signup", methods=["POST"])
def signup():
    username = request.json.get("username", None)
    password = request.json.get("password", None)
    loc_x = request.json.get("loc_x", None)
    loc_y = request.json.get("loc_y", None)

    try:
        session = Session(engine)
        user = Customer(username=username, password=password, loc_y=int(loc_y), loc_x=int(loc_x))
        session.add(user)
        session.commit()
        user_id = user.id
        session.close()
        print(user_id)
    except:
        print("problem")
        return jsonify({"msg": "Bad username or password"}), 401

    access_token = create_access_token(identity=user_id)
    # return jsonify(access_token=access_token)
    return render_template("homepage.html", access_token=access_token)


# --------------------------------------------------------------------------------


# --------------------------------------------------------------------------------
# Protect a route with jwt_required, which will kick out requests
# without a valid JWT present.
@app.route("/get_ride", methods=["GET"])
@jwt_required()
def getRide():
    current_user = get_jwt_identity()
    bike_id = request.json.get("bike_id", None)
    try:
        bike_id = int(bike_id)
    except:
        print("problem")
        return jsonify({"msg": "Format of ID is not correct"}), 401

    session = Session(engine)
    bike_obj = session.query(Bike).get(bike_id)
    if bike_obj is None:
        session.close()
        return jsonify({"msg": "Bike not found"}), 401
    if bike_obj.status != "available":
        session.close()
        return jsonify({"msg": "Bike is not available"}), 401

    user_obj = session.query(Customer).get(current_user)
    if haversine(bike_obj.loc_x, bike_obj.loc_y, user_obj.loc_x, user_obj.loc_y) < 100:
        user_obj.status = "riding"
        bike_obj.status = "busy"
        ride = Ride(customer_id=user_obj.id, bike_id=bike_obj.id, status="ongoing", date=func.current_date())
        session.add(ride)
        session.commit()
        ride_id = ride.id
        session.close()
        return jsonify({"msg": "ride_id:" + str(ride_id)}), 200
    session.close()
    return jsonify({"msg": "Bike is far from you"}), 401


@app.route("/end_ride", methods=["GET"])
@jwt_required()
def endRide():
    current_user = get_jwt_identity()
    ride_id = request.json.get("ride_id", None)
    bike_loc_x = int(request.json.get("loc_x", None))
    bike_loc_y = int(request.json.get("loc_y", None))
    try:
        ride_id = int(ride_id)
    except:
        print("problem")
        return jsonify({"msg": "Format of ID is not correct"}), 401
    session = Session(engine)
    ride_obj = session.query(Ride).get(ride_id)
    if ride_obj.customer_id != current_user:
        session.close()
        return jsonify({"msg": "You are not the rider"}), 401

    user_obj = session.query(Customer).get(current_user)
    bike_obj = session.query(Bike).get(ride_obj.bike_id)

    user_obj.status = "free"
    bike_obj.status = "available"
    ride_obj.status = "finished"
    ride_obj.distance = haversine(bike_obj.loc_x, bike_obj.loc_y, bike_loc_x, bike_loc_y)
    session.commit()

    riding = Riding(ride_obj)
    users_count = session.query(Customer).count()
    session.close()

    job = q.enqueue_call( func=pointing, args=(riding, users_count,), result_ttl=5000)
    print(job.get_id())

    return jsonify({"msg": "end of riding"}), 200


# --------------------------------------------------------------------------------


if __name__ == "__main__":
    # make_bikes()
    # session = Session(engine)
    # q = session.query(Bike).all()
    # print(f'bike {q}')
    # session.close()
    app.run()
