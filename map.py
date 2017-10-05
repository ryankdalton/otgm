import os
from datetime import datetime
from flask import Flask, request, flash, url_for, redirect, \
     render_template, abort
import gunicorn
import pg
import json
##from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config.from_pyfile('map.cfg')
print dir(app.config)


db = pg.connect(app.config['APP_NAME'], \
     app.config['PG_DB_HOST'], \
     app.config['PG_DB_PORT'], \
     None, \
     app.config['PG_DB_USERNAME'], \
     app.config['PG_DB_PASSWORD'] )



def postOrder(request):
    try:
        orderdetails = request.form # a multidict containing POST data

        emailaddress = request.form['pEmail']
        confirmemail = request.form['cEmail']
        mapname = request.form['mapname']
        maptype = request.form['maptype']
        maplicense = request.form['license']
        comments = request.form['comments']
    ##        fileUpload = request.form['fileupload']
        priceinput = request.form['priceinput']
        discountCode = request.form['pDiscount']
        mapgeom = request.form['mapgeom']


        pageOrientation = getPageOrientation(mapgeom)
        mapScale = getMapScale(mapgeom)

        sql = """INSERT INTO webapp.orders (emailaddress, maptype, license, mapname, orderdate, comments, price, discountcode, pageorientation, mapscale, geom) VALUES ($${emailaddress}$$, $${maptype}$$, $${maplicense}$$, $${mapname}$$, CURRENT_TIMESTAMP AT TIME ZONE 'MST', $${comments}$$, {priceinput}, $${discountCode}$$, $${pageOrientation}$$, {mapScale}, ST_GeomFromText($${mapgeom}$$, 4326) )""".format(emailaddress=emailaddress, maptype=maptype, maplicense=maplicense, mapname=mapname, comments=comments, priceinput=priceinput, discountCode=discountCode, pageOrientation=pageOrientation, mapScale=mapScale, mapgeom=mapgeom)

        db.query( sql )
        orderstatus = {'status': 'True'}
        ##customer = {'name': emailaddress}

    ##        #Send email to administrator
    ##        fromuser = app.config['MAIL_USERNAME']
    ##
    ##        gmail.sendemail("Order accepted", \
    ##        "Thank you for placing an order with us!  Your order has been accepted. You can expect to receive your personalized map in about 24 hours.", \
    ##        fromaddrs = [fromuser], \
    ##        toaddrs = [emailaddress], \
    ##        bccaddrs = ["info@offthegridmaps.com"])

        return orderstatus

    except:
        orderstatus = {'status': 'False'}


def getMapProjects(emailaddress, mapproject=None):
    try:
        emailaddress = emailaddress.replace("%27", "'")

        dbPartnerDetails = db.query("SELECT name, url, maptype FROM webapp.vw_partners where emailaddress like $$%{0}%$$".format(emailaddress))
        partner = dbPartnerDetails.dictresult()[0]

        if mapproject == None or mapproject == '':
            dbPublishedMaps = db.query("SELECT mapname, filename, 'static/download/' || filename || '.pdf' as url FROM webapp.vw_maporders where emailaddress like $$%{0}%$$ AND publish=1 AND processeddate IS NOT NULL order by filename".format(emailaddress))
        else:
            dbPublishedMaps = db.query("SELECT mapname, filename, 'static/download/' || filename || '.pdf' as url FROM webapp.vw_maporders where emailaddress like $$%{0}%$$ AND publish=1 AND processeddate IS NOT NULL AND mapproject = $${1}$$ order by filename".format(emailaddress, mapproject))

        partnerMaps = dbPublishedMaps.dictresult()
        return partner, partnerMaps

    except:
        return "Error retrieving map projects"


def getCustomerMaps(emailaddress):
    try:

        emailaddress = emailaddress.replace("%27", "'")
        customer = {'name': emailaddress}

        dbPublishedMaps = db.query("SELECT mapname, filename, 'static/download/' || filename || '.pdf' as url FROM webapp.vw_maporders where emailaddress = $${0}$$ AND processeddate IS NOT NULL order by filename".format(emailaddress))
        customerMaps = dbPublishedMaps.dictresult()

        return customer, customerMaps

    except:
        return "Error retrieving map projects"


def pgToGeoJSON(tablename, fields, limit=1000, whereClause="1=1"):
    try:

        sql="""SELECT row_to_json(fc)
         FROM ( SELECT 'FeatureCollection' As type, array_to_json(array_agg(f)) As features
         FROM (SELECT 'Feature' As type,
            ST_AsGeoJSON(lg.geom)::json As geometry,
            (
            select row_to_json(t)
            from ( select {fld} ) t
            )
            AS properties
            FROM {tn} As lg
            WHERE {wc}
            LIMIT {lim} ) As f
            )  As fc;""".format(tn=tablename, fld=fields, wc=whereClause, lim=limit)

        q = db.query(sql)
        result = q.getresult()
        return str( result[0][0] )

    except:
        return "ERROR: Could not return valid geojson"


def pgToGeoJsonBBox(tablename, fields, bboxString, limit=500, whereClause="1=1"):
    try:

        bbox = bboxString.split(",")

        sql="""SELECT row_to_json(fc)
         FROM ( SELECT 'FeatureCollection' As type, array_to_json(array_agg(f)) As features
             FROM (SELECT 'Feature' As type,
                ST_AsGeoJSON(lg.geom)::json As geometry,
                (
                select row_to_json(t)
                from ( select {fld} ) t
                )
                As properties
               FROM {tn} As lg
               WHERE ST_Intersects( ST_MakeEnvelope({lon1}, {lat1}, {lon2}, {lat2}, 4326), lg.geom)
               AND {wc}
               LIMIT {lim} )
             As f ) As fc;""".format(tn=tablename, fld=fields, wc=whereClause, lim=limit, lon1=bbox[0], lat1=bbox[1], lon2=bbox[2], lat2=bbox[3])

        q = db.query(sql)
        result = q.getresult()
        return str( result[0][0] )

    except:
        return "ERROR: Could not return valid geojson within BBOX"


def getPageOrientation(mapgeom):

    getPageLayout = """select CASE
            WHEN ( ST_XMax(ST_Transform(ST_GeomFromText($${mapgeom}$$,4326),32100)) - ST_XMin(ST_Transform(ST_GeomFromText($${mapgeom}$$,4326),32100)) ) > ( ST_YMax(ST_Transform(ST_GeomFromText($${mapgeom}$$,4326),32100)) - ST_YMin(ST_Transform(ST_GeomFromText($${mapgeom}$$,4326),32100)) ) THEN 'L'
            ELSE 'P'
            END AS pagelayout""".format(mapgeom=mapgeom)

    q = db.query(getPageLayout)
    result = q.getresult()
    pageOrientation = result[0][0]
    return pageOrientation




def getMapScale(mapGeom):

    def getFeatureOrientation(mapGeom):
        pageLayout = """select CASE
            WHEN ( ST_XMax(ST_Transform(ST_GeomFromText($${mapgeom}$$,4326),32100)) - ST_XMin(ST_Transform(ST_GeomFromText($${mapgeom}$$,4326),32100)) ) > ( ST_YMax(ST_Transform(ST_GeomFromText($${mapgeom}$$,4326),32100)) - ST_YMin(ST_Transform(ST_GeomFromText($${mapgeom}$$,4326),32100)) ) THEN 'L'
            ELSE 'P'
            END AS pagelayout""".format(mapgeom=mapGeom)

        q = db.query(pageLayout)
        result = q.getresult()
        featureOrientation = result[0][0]
        return featureOrientation

    def getPageSize(featureOrientation):
        if featureOrientation == "L":
            pageSize = {"pageX":17, "pageY":11}
        else:
            pageSize = {"pageX":11, "pageY":17}
        return pageSize


    def getMaxPageSize(pageSize):
        if pageSize.get("pageX") > pageSize.get("pageY"):
            maxPageSize = pageSize.get("pageX")
        else:
            maxPageSize = pageSize.get("pageY")
        return maxPageSize


    def getMaxFeatureDelta(mapGeom):
        getDeltaXY = """select
                ABS( ST_XMax(ST_Transform(ST_GeomFromText($${mapgeom}$$,4326),32100)) - ST_XMin(ST_Transform(ST_GeomFromText($${mapgeom}$$,4326),32100)) ) * 1.05 as deltaX,
                ABS( ST_YMax(ST_Transform(ST_GeomFromText($${mapgeom}$$,4326),32100)) - ST_YMin(ST_Transform(ST_GeomFromText($${mapgeom}$$,4326),32100)) ) * 1.05 as deltaY
            """.format(mapgeom=mapGeom)

        q = db.query(getDeltaXY)
        result = q.getresult()
        deltaX = result[0][0]
        deltaY = result[0][1]

        if deltaX > deltaY:
            maxDelta = deltaX
        else:
            maxDelta = deltaY
        return maxDelta


    def getMap2PageUnits(mapUnits, pageUnits):
        conversions = {"meters2inches":39.37, "feet2inches":12.0}

        if mapUnits == "Meters" and pageUnits=="Inches":
            cFactor = conversions.get("meters2inches")
        elif mapUnits == "Feet" and pageUnits=="Inches":
            cFactor = conversions.get("feet2inches")
        else:
            cFactor = 1.0

        return cFactor


    def getOptimalScale(mapGeom, mapUnits, pageSize, pageUnits, fBuffer=1.0):

        standardScales = [7920,15840,21120,31680,42240,47520,63360,79200,95040,110080,126720,158400,190080,253440,316800,380160,443520,506880,570240,633600]

        featureOrientation = getFeatureOrientation(mapGeom) #P
        ##print featureOrientation
        pageSize = getPageSize(featureOrientation) #11x17
        ##print pageSize
        maxPageSize = getMaxPageSize(pageSize) #17
        ##print maxPageSize
        maxFeatureDelta = getMaxFeatureDelta(mapGeom) #calced value
        ##print maxFeatureDelta
        map2PageUnits = getMap2PageUnits(mapUnits, pageUnits) #39.37
        ##print map2PageUnits


        featureScale = int( (maxFeatureDelta * map2PageUnits / maxPageSize) * fBuffer)
        print featureScale

        for scale in standardScales:
            if scale < featureScale:
                continue
            elif scale >= featureScale:
                optimalScale = scale
                break

        return optimalScale




    mapUnits = "Meters"
    pageOrientation = getPageOrientation(mapGeom)
    pageSize = getPageSize(pageOrientation)
    pageUnits = "Inches"

    optimalScale = getOptimalScale(mapGeom, mapUnits, pageSize, pageUnits, 1.15)
    return optimalScale




##################### Begin web page URLS #########################
@app.route('/', methods=['GET', 'POST'])
@app.route('/home', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
@app.route('/index.html', methods=['GET', 'POST'])
def index():

    try:
        params = request.args.to_dict()

        if request.method == 'POST':
            orderstatus = postOrder(request)
            return render_template('index.html', orderstatus=orderstatus)


        elif 'customer' in params:
            emailaddress = params['customer']
##            customer = {'name': emailaddress}
##            dbPublishedMaps = db.query("SELECT mapname, filename, 'static/download/' || filename || '.pdf' as url FROM webapp.vw_maporders where emailaddress = $${0}$$ AND processeddate IS NOT NULL order by filename".format(emailaddress))
##            customerMaps = dbPublishedMaps.dictresult()

            customer, customerMaps = getCustomerMaps(emailaddress)
            return render_template('index.html', customer=customer, customerMaps=customerMaps)

        elif 'partner' in params:
            emailaddress = params['partner']

##            dbPartnerDetails = db.query("SELECT name, url, maptype FROM webapp.vw_partners where emailaddress = $${0}$$".format(emailaddress))
##            partner = dbPartnerDetails.dictresult()[0]
##
##            dbPublishedMaps = db.query("SELECT mapname, filename, 'static/download/' || filename || '.pdf' as url FROM webapp.vw_maporders where emailaddress = $${0}$$ AND publish='1' AND processeddate IS NOT NULL order by filename".format(emailaddress))
##            partnerMaps = dbPublishedMaps.dictresult()

            partner, partnerMaps = getMapProjects(emailaddress)
            return render_template('index.html', partner=partner, partnerMaps=partnerMaps)

        else:
            return render_template('index.html')

    except:
        return render_template('404.html')



# ---------------- Other endpoint URLS --------------

@app.route('/bootstrap', methods=['GET'])
def bootstrap():

    try:
        return render_template('bootstrap.html')

    except:
        return render_template('404.html')


@app.route('/montanafishingmaps', methods=['GET'])
def montanafishingmaps():

    try:
        return render_template('montanafishingmaps.html')

    except:
        return render_template('404.html')


@app.route('/montanahuntingmaps', methods=['GET'])
def montanahuntingmaps():

    try:
        return render_template('montanahuntingmaps.html')

    except:
        return render_template('404.html')


@app.route('/montanahikingmaps', methods=['GET'])
def montanahikingmaps():

    try:
        return render_template('montanahikingmaps.html')

    except:
        return render_template('404.html')

# ---------------- Partner URLS --------------


@app.route('/larys', methods=['GET', 'POST'])
def larys():

    try:
        if request.method == 'POST':
            orderstatus = postOrder(request)
            return render_template('index.html', orderstatus=orderstatus)

        else:
            emailaddress = 'larysflyandsupply@gmail.com'
            partner, partnerMaps = getMapProjects(emailaddress)
            return render_template('index.html', partner=partner, partnerMaps=partnerMaps)

    except:
        return render_template('404.html')


@app.route('/sleddogracing', methods=['GET', 'POST'])
def sleddogracing():

    try:
        if request.method == 'POST':
            orderstatus = postOrder(request)
            return render_template('index.html', orderstatus=orderstatus)

        else:
            emailaddress = 'info@offthegridmaps.com'
            mapproject = 'sleddogracing'
            partner, partnerMaps = getMapProjects(emailaddress,mapproject)
            return render_template('index.html', partner=partner, partnerMaps=partnerMaps)

    except:
        return render_template('404.html')


@app.route('/lakestream', methods=['GET', 'POST'])
def lakestream():

    try:
        if request.method == 'POST':
            orderstatus = postOrder(request)
            return render_template('index.html', orderstatus=orderstatus)

        else:
            emailaddress = 'lakestream.com'
            partner, partnerMaps = getMapProjects(emailaddress)
            return render_template('index.html', partner=partner, partnerMaps=partnerMaps)

    except:
        return render_template('404.html')



@app.route('/glaciergundogclub', methods=['GET', 'POST'])
def glaciergundogclub():

    try:
        if request.method == 'POST':
            orderstatus = postOrder(request)
            return render_template('index.html', orderstatus=orderstatus)

        else:
            emailaddress = 'info@offthegridmaps.com'
            mapproject = 'glaciergundogclub'
            partner, partnerMaps = getMapProjects(emailaddress,mapproject)
            return render_template('index.html', partner=partner, partnerMaps=partnerMaps)

    except:
        return render_template('404.html')



##@app.route('/grizzlyhackle', methods=['GET', 'POST'])
##def grizzlyhackle():
##
##    try:
##        if request.method == 'POST':
##            orderstatus = postOrder(request)
##            return render_template('index.html', orderstatus=orderstatus)
##
##        else:
##            emailaddress = 'info@grizzlyhackle.com'
##            partner, partnerMaps = getMapProjects(emailaddress)
##            return render_template('index.html', partner=partner, partnerMaps=partnerMaps)
##
##    except:
##        return render_template('404.html')


##@app.route('/glaciercyclery', methods=['GET', 'POST'])
##def glaciercyclery():
##
##    try:
##        if request.method == 'POST':
##            orderstatus = postOrder(request)
##            return render_template('index.html', orderstatus=orderstatus)
##
##        else:
##            emailaddress = 'info@glaciercyclery.com'
##            partner, partnerMaps = getMapProjects(emailaddress)
##            return render_template('index.html', partner=partner, partnerMaps=partnerMaps)
##
##    except:
##        return render_template('404.html')


@app.route('/bigforkanglers', methods=['GET', 'POST'])
def bigforkanglers():

    try:
        if request.method == 'POST':
            orderstatus = postOrder(request)
            return render_template('index.html', orderstatus=orderstatus)

        else:
            emailaddress = 'bigforkanglers@yahoo.com'
            partner, partnerMaps = getMapProjects(emailaddress)
            return render_template('index.html', partner=partner, partnerMaps=partnerMaps)

    except:
        return render_template('404.html')
# ---------------- Sample map URLS --------------

##@app.route('/samples', methods=['GET', 'POST'])
##def samples():
##
##    try:
##        if request.method == 'POST':
##            orderstatus = postOrder(request)
##            return render_template('index.html', orderstatus=orderstatus)
##
##        else:
##            emailaddress = 'info@offthegridmaps.com'
##            partner, partnerMaps = getMapProjects(emailaddress)
##            return render_template('index.html', partner=partner, partnerMaps=partnerMaps)
##
##    except:
##        return render_template('404.html')


@app.route('/onthesnow', methods=['GET', 'POST'])
@app.route('/skiing', methods=['GET', 'POST'])
def onthesnow():

    try:
        if request.method == 'POST':
            orderstatus = postOrder(request)
            return render_template('index.html', orderstatus=orderstatus)

        else:
            emailaddress = 'info@offthegridmaps.com'
            mapproject = 'onthesnow'
            partner, partnerMaps = getMapProjects(emailaddress, mapproject)
            return render_template('index.html', partner=partner, partnerMaps=partnerMaps)

    except:
        return render_template('404.html')


@app.route('/onthetrail', methods=['GET', 'POST'])
@app.route('/hiking', methods=['GET', 'POST'])
def onthetrail():

    try:
        if request.method == 'POST':
            orderstatus = postOrder(request)
            return render_template('index.html', orderstatus=orderstatus)

        else:
            emailaddress = 'info@offthegridmaps.com'
            mapproject = 'onthetrail'
            partner, partnerMaps = getMapProjects(emailaddress, mapproject)
            return render_template('index.html', partner=partner, partnerMaps=partnerMaps)

    except:
        return render_template('404.html')


@app.route('/onthewater', methods=['GET', 'POST'])
@app.route('/boating', methods=['GET', 'POST'])
def onthewater():

    try:
        if request.method == 'POST':
            orderstatus = postOrder(request)
            return render_template('index.html', orderstatus=orderstatus)

        else:
            emailaddress = 'info@offthegridmaps.com'
            mapproject = 'onthewater'
            partner, partnerMaps = getMapProjects(emailaddress, mapproject)
            return render_template('index.html', partner=partner, partnerMaps=partnerMaps)

    except:
        return render_template('404.html')



@app.route('/onthehook', methods=['GET', 'POST'])
@app.route('/fishing', methods=['GET', 'POST'])
def onthehook():

    try:
        if request.method == 'POST':
            orderstatus = postOrder(request)
            return render_template('index.html', orderstatus=orderstatus)

        else:
            emailaddress = 'info@offthegridmaps.com'
            mapproject = 'onthehook'
            partner, partnerMaps = getMapProjects(emailaddress, mapproject)
            return render_template('index.html', partner=partner, partnerMaps=partnerMaps)

    except:
        return render_template('404.html')


@app.route('/onthehunt', methods=['GET', 'POST'])
@app.route('/hunting', methods=['GET', 'POST'])
def onthehunt():

    try:
        if request.method == 'POST':
            orderstatus = postOrder(request)
            return render_template('index.html', orderstatus=orderstatus)

        else:
            emailaddress = 'info@offthegridmaps.com'
            mapproject = 'onthehunt'
            partner, partnerMaps = getMapProjects(emailaddress, mapproject)
            return render_template('index.html', partner=partner, partnerMaps=partnerMaps)

    except:
        return render_template('404.html')


@app.route('/onthebike', methods=['GET', 'POST'])
@app.route('/biking', methods=['GET', 'POST'])
def onthebike():

    try:
        if request.method == 'POST':
            orderstatus = postOrder(request)
            return render_template('index.html', orderstatus=orderstatus)

        else:
            emailaddress = 'info@offthegridmaps.com'
            mapproject = 'onthebike'
            partner, partnerMaps = getMapProjects(emailaddress, mapproject)
            return render_template('index.html', partner=partner, partnerMaps=partnerMaps)

    except:
        return render_template('404.html')


@app.route('/status', methods=['GET'])
def status():
    try:
        statusMessage = '<strong>Status = 200 OK</strong>'
        print statusMessage

        pendingCount = 0
        tablename = "webapp.vw_pendingorders"
        pendingOrders = db.query("SELECT emailaddress, ordercount FROM {0};".format(tablename)).getresult()

        if len(pendingOrders) > 0:
            pendingMessage = ""
            for orderDetails in pendingOrders:
                pendingMessage += "<i>{0} ({1})</i><br>".format(orderDetails[0],orderDetails[1])
                pendingCount += orderDetails[1]
            ##print "Pending orders = {0}".format(pendingCount)
            pendingMessage = "<strong>Pending orders = {0}</strong><br>{1}".format(pendingCount, pendingMessage)
            return pendingMessage
        else:
            pendingMessage = "<strong>Pending orders = {0}</strong>".format(pendingCount)
            ##print "Pending orders = {0}".format(pendingCount)

        return statusMessage

    except:
        return render_template('404.html')



#return record count of pending orders:
@app.route("/pending", methods=['GET'])
def pending():
    try:
        pendingCount = 0
        tablename = "webapp.vw_pendingorders"
        pendingOrders = db.query("SELECT emailaddress, ordercount FROM {0};".format(tablename)).getresult()

        if len(pendingOrders) > 0:
            pendingMessage = ""
            for orderDetails in pendingOrders:
                pendingMessage += "<i>{0} ({1})</i><br>".format(orderDetails[0],orderDetails[1])
                pendingCount += orderDetails[1]
            ##print "Pending orders = {0}".format(pendingCount)
            pendingMessage = "<strong>Pending orders = {0}</strong><br>{1}".format(pendingCount, pendingMessage)
            return pendingMessage
        else:
            pendingMessage = "<strong>Pending orders = {0}</strong>".format(pendingCount)
            ##print "Pending orders = {0}".format(pendingCount)
            return pendingMessage

    except:
        return render_template('404.html')






# ---------------- GeoJSON data layers --------------

#return state boundary:
@app.route("/data/pgstate")
def pgstate():
    try:
        tablename = "webdata.msdi_state"
        fields = "name"
        return pgToGeoJSON(tablename, fields)
    except:
        return "ERROR: Could not return valid state.geojson"

##@app.route("/data/pgstate")
##def pgstate():
##    try:
##        bboxString = str( request.args.get('bbox') )
##        tablename = "webdata.msdi_state"
##        fields = "name"
##        return pgToGeoJsonBBox(tablename, fields, bboxString)
##    except:
##        return "ERROR: Could not return valid state.geojson"

@app.route("/data/pgstatehd")
def pgstatehd():
    try:
        bboxString = str( request.args.get('bbox') )
        tablename = "webdata.msdi_statehd"
        fields = "name"
        return pgToGeoJsonBBox(tablename, fields, bboxString)
    except:
        return "ERROR: Could not return valid state.geojson"



#return counties:
@app.route("/data/pgcounties")
def pgcounties():
    try:
        bboxString = str( request.args.get('bbox') )
        tablename = "webdata.msdi_counties"
        fields = "name"
        return pgToGeoJsonBBox(tablename, fields, bboxString)
    except:
        return "ERROR: Could not return valid counties.geojson"

@app.route("/data/pgcountieshd")
def pgcountieshd():
    try:
        bboxString = str( request.args.get('bbox') )
        tablename = "webdata.msdi_countieshd"
        fields = "name"
        return pgToGeoJsonBBox(tablename, fields, bboxString)
    except:
        return "ERROR: Could not return valid counties.geojson"



#return FWP Block Management Areas:
@app.route("/data/pgbma")
def pgbma():

    try:
        bboxString = str( request.args.get('bbox') )
        tablename = "webdata.fwp_bma"
        fields = "labelname, region, permission, accessinfo, pdflink"
        return pgToGeoJsonBBox(tablename, fields, bboxString, 1000)
    except:
        return "ERROR: Could not return valid bma.geojson"

@app.route("/data/pgbmahd")
def pgbmahd():

    try:
        bboxString = str( request.args.get('bbox') )
        tablename = "webdata.fwp_bmahd"
        fields = "labelname, region, permission, accessinfo, pdflink"
        return pgToGeoJsonBBox(tablename, fields, bboxString, 1000)
    except:
        return "ERROR: Could not return valid bma.geojson"

#return all FWP Upland Bird Game Enhancement Program:
@app.route("/data/pgugbep")
def pgugbep():

    try:
        bboxString = str( request.args.get('bbox') )
        tablename = "webdata.fwp_ugbep"
        fields = "labelname, region, permission, cooperator, contact, pdflink"
        return pgToGeoJsonBBox(tablename, fields, bboxString, 200)
    except:
        return "ERROR: Could not return valid ugbep.geojson"

#return all FWP Upland Bird Game Enhancement Program:
@app.route("/data/pgugbephd")
def pgugbephd():

    try:
        bboxString = str( request.args.get('bbox') )
        tablename = "webdata.fwp_ugbephd"
        fields = "labelname, region, permission, cooperator, contact, pdflink"
        return pgToGeoJsonBBox(tablename, fields, bboxString, 200)
    except:
        return "ERROR: Could not return valid ugbephd.geojson"

#return all FWP Wildlife Management Areas:
@app.route("/data/pgwma")
def pgwma():

    try:
        bboxString = str( request.args.get('bbox') )
        tablename = "webdata.fwp_wma"
        fields = "name, region, web_page"
        return pgToGeoJsonBBox(tablename, fields, bboxString, 200)
    except:
        return "ERROR: Could not return valid wma.geojson"



#return FWP License Providers
@app.route("/data/pglicense")
def pglicense():

    try:
        bboxString = str( request.args.get('bbox') )
        tablename = "webdata.fwp_license"
        fields = "business, phone, address, city, state, zipcode, holidays, seasonal"
        return pgToGeoJsonBBox(tablename, fields, bboxString)

    except:
        return "ERROR: Could not return valid licenseproviders.geojson"


#return Public Lands as singlepart features:
@app.route("/data/pgpublands")
def pgpublands():
    try:
        bboxString = str( request.args.get('bbox') )
        tablename = "webdata.mnhp_publiclands"
        fields = "ownername, ownertype"
        return pgToGeoJsonBBox(tablename, fields, bboxString, 2000)
    except:
        return "ERROR: Could not return valid publiclands.geojson"


#return Public Lands as singlepart features:
@app.route("/data/pgpublandshd")
def pgpublandshd():
    try:
        bboxString = str( request.args.get('bbox') )
        tablename = "webdata.mnhp_publiclandshd"
        fields = "ownername,ownertype"
        return pgToGeoJsonBBox(tablename, fields, bboxString, 1000)
    except:
        return "ERROR: Could not return valid publiclands.geojson"


#return all trails:
@app.route("/data/pgtrails")
def pgtrails():

    try:
        bboxString = str( request.args.get('bbox') )
        whereClause =str( request.args.get('whereClause') )
        tablename = "webdata.msdi_trails"
        fields = "labelname, miles, season"
        return pgToGeoJsonBBox(tablename, fields, bboxString, 1000, whereClause)
    except:
        return "ERROR: Could not return valid trails.geojson"


#return trails filtered by bbox:
@app.route("/data/pgtrailshd")
def pgtrailshd():

    try:
        bboxString = str( request.args.get('bbox') )
        whereClause =str( request.args.get('whereClause') )
        tablename = "webdata.msdi_trailshd"
        fields = "labelname, miles, season"
        return pgToGeoJsonBBox(tablename, fields, bboxString, 500, whereClause)
    except:
        return "ERROR: Could not return valid trailshd.geojson"


#return all Rec Sites:
@app.route("/data/pgrecsites")
def pgrecsites():

    try:
        bboxString = str( request.args.get('bbox') )
        tablename = "webdata.mvw_recsites"
        fields = "labelname, sitetype, source"
        return pgToGeoJsonBBox(tablename, fields, bboxString, 500)
    except:
        return "ERROR: Could not return valid recsites.geojson"

#return Boating/Fishing Rec Sites:
@app.route("/data/pgfishing")
def pgfishing():
    try:
        bboxString = str( request.args.get('bbox') )
        tablename = "webdata.mvw_recsites"
        fields = "labelname, sitetype, source"
        whereClause = "SiteClass IN ('Boating','Fishing')"
        return pgToGeoJsonBBox(tablename, fields, bboxString, 200, whereClause)
    except:
        return "ERROR: Could not return valid fishing.geojson"


#return Camping/Day Use Rec Sites:
@app.route("/data/pgcamping")
def pgcamping():
    try:
        bboxString = str( request.args.get('bbox') )
        tablename = "webdata.mvw_recsites"
        fields = "labelname, sitetype, source"
        whereClause = "SiteClass IN ('Camping','Day Use')"
        return pgToGeoJsonBBox(tablename, fields, bboxString, 200, whereClause)
    except:
        return "ERROR: Could not return valid camping.geojson"


#return Hiking Rec Sites:
@app.route("/data/pghiking")
def pghiking():
    try:
        bboxString = str( request.args.get('bbox') )
        tablename = "webdata.mvw_recsites"
        fields = "labelname, sitetype, source"
        whereClause = "SiteClass IN ('Hiking')"
        return pgToGeoJsonBBox(tablename, fields, bboxString, 200, whereClause)
    except:
        return "ERROR: Could not return valid hiking.geojson"


#return Other Rec Sites:
@app.route("/data/pgother")
def pgother():
    try:
        bboxString = str( request.args.get('bbox') )
        tablename = "webdata.mvw_recsites"
        fields = "labelname, sitetype, source"
        whereClause = "SiteClass IN ('Information', 'Land Management', 'Transportation')"
        return pgToGeoJsonBBox(tablename, fields, bboxString, 200, whereClause)
    except:
        return "ERROR: Could not return valid otherpoi.geojson"


#return Winter Sports Rec Sites:
@app.route("/data/pgwinter")
def pgwinter():
    try:
        bboxString = str( request.args.get('bbox') )
        tablename = "webdata.mvw_recsites"
        fields = "labelname, sitetype, source"
        whereClause = "SiteClass IN ('Winter Sports')"
        return pgToGeoJsonBBox(tablename, fields, bboxString, 200, whereClause)
    except:
        return "ERROR: Could not return valid winter.geojson"


#return Spring Turkey districts:
@app.route("/data/pgturkeyspring")
def pgturkeyspring():
    try:
        bboxString = str( request.args.get('bbox') )
        tablename = "webdata.fwp_turkeyspring"
        fields = "reg, name, harvtype_s, webpage"
        return pgToGeoJsonBBox(tablename, fields, bboxString, 200)
    except:
        return "ERROR: Could not return valid turkeyspring.geojson"


#return Fall Turkey districts:
@app.route("/data/pgturkeyfall")
def pgturkeyfall():
    try:
        bboxString = str( request.args.get('bbox') )
        tablename = "webdata.fwp_turkeyfall"
        fields = "reg, name, harvtype_f, webpage"
        return pgToGeoJsonBBox(tablename, fields, bboxString, 200)
    except:
        return "ERROR: Could not return valid turkeyfall.geojson"


#return Turkey habitat:
@app.route("/data/pgturkeyhabitat")
def pgturkeyhabitat():
    try:
        bboxString = str( request.args.get('bbox') )
        tablename = "webdata.fwp_turkeyhabitat"
        fields = "region, species, habqual"
        return pgToGeoJsonBBox(tablename, fields, bboxString, 200)
    except:
        return "ERROR: Could not return valid turkeyhabitat.geojson"


#return Deer and Elk districts:
@app.route("/data/pgdeerelk")
def pgdeerelk():
    try:
        bboxString = str( request.args.get('bbox') )
        tablename = "webdata.fwp_deerelk"
        fields = "reg, district, labelname, area_mi, deerwebpag, elkwebpage"
        return pgToGeoJsonBBox(tablename, fields, bboxString, 200)
    except:
        return "ERROR: Could not return valid deerelk.geojson"


#return Deer and Elk districts in HD:
@app.route("/data/pgdeerelkhd")
def pgdeerelkhd():
    try:
        bboxString = str( request.args.get('bbox') )
        tablename = "webdata.fwp_deerelkhd"
        fields = "reg, district, labelname, area_mi, deerwebpag, elkwebpage"
        return pgToGeoJsonBBox(tablename, fields, bboxString, 200)
    except:
        return "ERROR: Could not return valid deerelk.geojson"

# ---------------- Application pages --------------

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


##@app.route('/test', methods=['GET', 'POST'])
##def test():
##
##    try:
##        if request.method == 'POST':
##            orderstatus = postOrder(request)
##            return orderstatus
##
##        else:
##            emailaddress = 'info@offthegridmaps.com'
##            partner, partnerMaps = getMapProjects(emailaddress)
##            return partner, partnerMaps
##
##    except:
##        return render_template('404.html')



##@app.route('/static/<path:resource>')
##def serveStaticResource(resource):
##    return send_from_directory('static/', resource)
##
##@app.route ('/redirect')
##def redirect():
##    return redirect('?customer=lakestream', code=302)


##@app.route('/gps', methods=['GET'])
##def gps():
##
##    try:
##        tab = {'name': 'gps'}
##        return render_template('index.html')
##    except:
##        return render_template('404.html')



@app.errorhandler(404)
def pageNotFound(error):
    try:
        return render_template('404.html')
    except:
        return "ERROR: Could not find correct page"





##@app.route ('/feedback')
##def feedback():
##    feedback = {'feedback': 'true'}
##    return redirect('index.html', feedback=feedback)


if __name__ == '__main__':
    app.run()