import os
from datetime import datetime
from flask import Flask, request, flash, url_for, redirect, \
     render_template, abort
import pg
import json

app = Flask(__name__)
app.config.from_pyfile('map.cfg')
print dir(app.config)


db = pg.connect(app.config['APP_NAME'], \
     app.config['PG_DB_HOST'], \
     app.config['PG_DB_PORT'], \
     None, None, \
     app.config['PG_DB_USERNAME'], \
     app.config['PG_DB_PASSWORD'] )


@app.route('/')
@app.route('/index')
def index():
    ##return render_template('index.html')
    return render_template('hello world')


##    params = request.args.to_dict()
##
##
##    if 'download' in params:
##        download = {'filename': params['download'], 'url': url_for('static', filename='download/{0}'.format(params['download']))}
##        return render_template('index.html', download=download)
##
####    elif 'customer' in params:
####        return redirect('/{0}'.format(params['customer']), code=301)
##
##    else:
##        return render_template('index.html')





@app.route('/static/<path:resource>')
def serveStaticResource(resource):
    return send_from_directory('static/', resource)

@app.route ('/redirect')
def redirect():
    return redirect('?customer=lakestream', code=302)


@app.route("/test")
def test():
    return "<strong>It's Alive!</strong>"



###return all parks:
##@app.route("/parks")
##def parks():
##    table_name = app.config['APP_NAME']
##    #query the DB for all the parkpoints
##    result = db.query('SELECT gid,name,ST_X(the_geom) as lon,ST_Y(the_geom) as lat FROM '+ table_name+";")
##
##    #Now turn the results into valid JSON
##    return str(json.dumps(list(result.dictresult())))
##
##
###bounding box (within?lat1=45.5&lon1=-82&lat2=46.5&lon2=-81)
##@app.route("/parks/within")
##def within():
##    table_name = app.config['APP_NAME']
##    #get the request parameters
##    lat1 = str(request.args.get('lat1'))
##    lon1 = str(request.args.get('lon1'))
##    lat2 = str(request.args.get('lat2'))
##    lon2 = str(request.args.get('lon2'))
##    limit = 25
##
##    #use the request parameters in the query
##    result = db.query("SELECT gid,name,ST_X(the_geom) as lon,ST_Y(the_geom) as lat FROM "+table_name+" t WHERE ST_Intersects( \
##        ST_MakeEnvelope("+lon1+", "+lat1+", "+lon2+", "+lat2+", 4326), t.the_geom) LIMIT "+str(limit)+";")
##
##    #turn the results into valid JSON
##    return str(json.dumps(list(result.dictresult())))




###return state boundary
##@app.route("/24k")
##def state():
##    ##table_name = app.config['APP_NAME']
##    table_name = 'webapp.quads100k'
##    #query the DB for all the parkpoints
##    result = db.query('SELECT gid, name_100k, geom FROM '+ table_name+";")
##
##    #Now turn the results into valid JSON
##    return str(json.dumps(list(result.dictresult())))
##
##
##@app.route('/order', methods=['GET', 'POST'])
##def order():
##    if request.method == 'POST':
##            todo = Todo(request.form['title'], request.form['text'])
##            db.session.add(todo)
##            db.session.commit()
##            return redirect(url_for('order'))
##    return render_template('order.html')



##@app.route('/login', methods=['GET', 'POST'])
##def login():
##    form = LoginForm()
##    if form.validate_on_submit():
##        flash('Login requested for OpenID="%s", remember_me=%s' %
##              (form.openid.data, str(form.remember_me.data)))
##        return redirect('/index')
##    return render_template('login.html',
##                           title='Sign In',
##                           form=form)


@app.route('/lakestream')
def lakestream():
    customer = {'name': 'Lakestream Fly Shop', 'url': 'http://www.lakestream.com/', 'maptype':'fishing'}
    return render_template('index.html', customer=customer)

##    if request.method == 'GET':
##        dbCustomerDetails = db.query("SELECT name, url, maptype FROM webapp.\"vw_customerDetails\" where emailaddress like '%lakestream.com'")
##        customer = dbCustomerDetails.dictresult()[0]
##
##        dbPublishedMaps = db.query("SELECT mapname, filename, url FROM webapp.\"vw_publishedmaps\" where emailaddress like '%lakestream.com' order by filename")
##        customerMaps = dbPublishedMaps.dictresult()
##
##    return render_template('index.html', customer=customer, customerMaps=customerMaps)


@app.route('/larys')
def larys():
    customer = {'name': 'Lary\'s Fly and Supply', 'url': 'https://www.facebook.com/larysflyandsupply/','maptype':'fishing'}
    return render_template('index.html', customer=customer)

##    if request.method == 'GET':
##        dbCustomerDetails = db.query("SELECT name, url, maptype FROM webapp.\"vw_customerDetails\" where emailaddress like '%lakestream.com'")
##        customer = dbCustomerDetails.dictresult()[0]
##
##        dbPublishedMaps = db.query("SELECT mapname, filename, url FROM webapp.\"vw_publishedmaps\" where emailaddress like '%lakestream.com' order by filename")
##        customerMaps = dbPublishedMaps.dictresult()
##
##    return render_template('index.html', customer=customer, customerMaps=customerMaps)



if __name__ == '__main__':
    app.run()
