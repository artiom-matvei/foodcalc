import functools
import os
import sqlite3
import sys

from flask import Flask, g, render_template, current_app, request, json, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config.from_mapping(
    DATABASE=os.path.join(app.instance_path, 'foodcalc2.sqlite'),
    SECRET_KEY="fgaeqjfvciu32149"
)

try:
    os.makedirs(app.instance_path)
except OSError:
    pass


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    return g.db


@app.route('/')
def all_foods():
    db = get_db()
    foods = db.execute('SELECT FoodID, FoodDescription, FoodDescriptionF FROM food_name').fetchall()
    return render_template('foods.html', foods=foods)


@app.route('/<int:id>/<float:serving_amount>/<int:measure_id>', methods=('GET', 'POST'))
@app.route('/<int:id>/<float:serving_amount>', methods=('GET', 'POST'))
@app.route('/<int:id>', methods=('GET', 'POST'))
def one_food(id, serving_amount=100., measure_id=1455):
    if request.method == 'POST':
        serving_amount = request.form['serving_amount']

        return redirect(url_for('one_food', id=id, serving_amount=serving_amount))

    db = get_db()
    food = db.execute(
        'SELECT FoodID, FoodDescription, FoodDescriptionF FROM food_name WHERE FoodID = ?', (id,)
    ).fetchone()
    nutrients = db.execute(
        'SELECT l.NutrientID, NutrientName, NutrientValue, NutrientUnit '
        'from nutrient_amount l inner join nutrient_name on l.NutrientID = nutrient_name.NutrientID '
        'where FoodID=?', (id,)
    ).fetchall()

    for i in range(nutrients.__len__()):
        nutrients[i] = (nutrients[i][0], nutrients[i][1], nutrients[i][2] * (serving_amount / 100), nutrients[i][3])

    return render_template('one_food.html', food=food, nutrients=nutrients, json_nutrients=json.dumps(nutrients),
                           serving_amount=serving_amount)


@app.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None

        if not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'
        elif db.execute('SELECT id FROM user WHERE username = ?',
                        (username,)
                        ).fetchone() is not None:
            error = 'User {} is already registered.'.format(username)

        if error is None:
            db.execute(
                'INSERT INTO user (username, password) VALUES (?, ?)',
                (username, generate_password_hash(password))
            )
            db.commit()
            return redirect(url_for('login'))

        flash(error)

    return render_template('register.html')


@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None
        user = db.execute(
            'SELECT * FROM user WHERE username = ?', (username,)
        ).fetchone()

        if user is None:
            error = 'Incorrect username.'
        elif not check_password_hash(user['password'], password):
            error = 'Incorrect password.'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('all_foods'))

        flash(error)

    return render_template('login.html')


@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            'SELECT * FROM user where id = ?', (user_id,)
        ).fetchone()


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('login'))

        return view(**kwargs)

    return wrapped_view


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('all_foods'))


@app.route('/dri', methods=('GET', 'POST'))
@login_required
def dri():
    db = get_db()
    user_id = session.get('user.id')
    nutrient_dri: list = db.execute('SELECT NutrientID, DRI FROM user_dri WHERE UserID = ?', (user_id,)).fetchall()
    joined_dri = db.execute(
        'SELECT nutrient_name.NutrientID, DRI, NutrientUnit, NutrientName from nutrient_name '
        'LEFT JOIN ( SELECT * FROM user_dri  WHERE UserID=2 ) as ud '
        'on nutrient_name.NutrientID = ud.NutrientID'
    ).fetchall()

    nutrient_dri_dict: dict = {nutrient['NutrientID']: nutrient['DRI'] for nutrient in nutrient_dri}

    nutrient_names: list = db.execute('SELECT NutrientID, NutrientCode, NutrientSymbol, NutrientUnit, NutrientName, '
                                      'NutrientNameF, Tagname, NutrientDecimals FROM nutrient_name').fetchall()
    nutrient_names_dict = {
        nutrient['NutrientID']: {'NutrientName': nutrient['NutrientName'], 'NutrientUnit': nutrient['NutrientUnit']} for
        nutrient in nutrient_names}

    if request.method == 'POST':
        for nutrient in joined_dri:
            if str(nutrient['NutrientID']) in request.form:
                #print('inside if', file=sys.stderr)
                print(request.form[str(nutrient['NutrientID'])], file=sys.stderr)

        # db.executemany('INSERT INTO user_dri (UserID, NutrientID, DRI) VALUES (?,?,?)'
        #                'ON CONFLICT(UserID,NutrientID) DO '
        #                'UPDATE SET (UserID, NutrientID, DRI) = (?,?,?)',)

    return render_template('dri.html', joined_dri=joined_dri)


if __name__ == '__main__':
    app.run(debug=True)
