import functools
import os
import sqlite3
import sys
from jinjasql import JinjaSql

from flask import Flask, g, render_template, current_app, request, json, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
j = JinjaSql(param_style='pyformat')
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
    db = get_db()

    if request.method == 'POST':
        if request.form['action'] == "Update nutrient amounts":
            serving_amount = request.form['serving_amount']
            print('Update nutrient amounts', file=sys.stderr)
            return redirect(url_for('one_food', id=id, serving_amount=serving_amount))
        elif request.form['action'] == "Add food":
            print('Add food', file=sys.stderr)
            db.execute(
                'INSERT INTO user_eaten (user_id, food_id, grams, date_of_consumption, date_of_entry) '
                'VALUES (?,?,?,?,?)',
                (session.get('user_id'), id, serving_amount, request.form['eaten_date'], request.form['eaten_date'])
            )
            db.commit()
            return redirect(url_for('eaten_food'))

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
    user_id = session.get('user_id')
    joined_dri = db.execute(
        'SELECT nutrient_name.NutrientID, DRI, NutrientUnit, NutrientName from nutrient_name '
        'LEFT JOIN ( SELECT * FROM user_dri  WHERE UserID=? ) as ud '
        'on nutrient_name.NutrientID = ud.NutrientID', (user_id,)
    ).fetchall()

    if request.method == 'POST':
        insert_list = []
        for nutrient in joined_dri:
            nutrient_id_str = str(nutrient['NutrientID'])
            nutrient_amount = request.form[nutrient_id_str]
            cond_a = nutrient_id_str in request.form
            cond_b = nutrient_amount.__ne__('')
            if cond_a and cond_b:
                insert_list.append(
                    (user_id, nutrient_id_str, nutrient_amount, user_id, nutrient_id_str, nutrient_amount))

        db.executemany('INSERT INTO user_dri (UserID, NutrientID, DRI) VALUES (?,?,?)'
                       'ON CONFLICT(UserID,NutrientID) DO '
                       'UPDATE SET (UserID, NutrientID, DRI) = (?,?,?)', insert_list)
        db.commit()

        return redirect(url_for('dri'))

    return render_template('dri.html', joined_dri=joined_dri)


@app.route('/eatenfood', methods=('GET', 'POST'))
@login_required
def eaten_food():
    db = get_db()
    user_id = str(session.get('user_id'))
    if request.method == 'POST':
        eaten_food_id = request.form['action']
        print(eaten_food_id, file=sys.stderr)
        db.execute('DELETE FROM user_eaten WHERE id=?', (eaten_food_id,))
        db.commit()

        return redirect(url_for('eaten_food'))

    nutrient_dri = db.execute('SELECT user_dri.NutrientID, DRI, NutrientName, NutrientUnit FROM user_dri '
                              'JOIN nutrient_name nn ON user_dri.NutrientID = nn.NutrientID WHere UserID=?',
                              (user_id,)).fetchall()

    # noinspection SqlResolve
    template = """SELECT ID, FOOD_ID, FoodDescription, GRAMS {% for nutrientID in nutrientIDS %}, IFNULL( MAX(CASE WHEN na.NutrientID={{ nutrientID }} THEN GRAMS*na.NutrientValue/100 END),0) as '{{ nutrientID }}' {% endfor %}, DATE_OF_CONSUMPTION FROM user_eaten ue JOIN food_name fn ON fn.FoodID=ue.food_id JOIN nutrient_amount na on fn.FoodID = na.FoodID WHERE user_id={{ userID }} GROUP BY ue.id"""
    data = {'nutrientIDS': [nutrient['NutrientID'] for nutrient in nutrient_dri],
            'userID': user_id}
    query, bind_params = j.prepare_query(template, data)

    eaten_food_db = db.execute(query % bind_params).fetchall()

    nutrient_totals = {id: sum(filter(None, [d[str(id)] for d in eaten_food_db])) for id in data['nutrientIDS']}

    nutrient_dri_dict = {
        e['NutrientID']:
            {'DRI': e['DRI'], 'NutrientName': e['NutrientName'], 'NutrientUnit': e['NutrientUnit']}
        for e in nutrient_dri}

    nutrient_dri_perc_dict = {id: nutrient_totals[id] / nutrient_dri_dict[id]['DRI']
                              for id in data['nutrientIDS']}

    return render_template('eaten_food.html', eaten_food_db=eaten_food_db, nutrient_totals=nutrient_totals,
                           nutrient_dri_perc_dict=nutrient_dri_perc_dict, nutrient_num_IDS=data['nutrientIDS'],
                           nutrient_str_IDS=[str(nid) for nid in data['nutrientIDS']],
                           nutrient_dri_dict=nutrient_dri_dict)


if __name__ == '__main__':
    app.run()
