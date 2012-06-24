# -*- coding: utf-8 -*-
from flask import Flask, send_file, safe_join, render_template, request
import sqlite3
from StringIO import StringIO
import os
import cv
from itertools import groupby

from models import InvCard, FixLog
from elixir import session

app = Flask(__name__)

@app.route('/db_image/<int:img_id>')
def db_image(img_id):
	connection = sqlite3.connect('inventory.sqlite3')
	cursor = connection.cursor()
	cursor.execute('select scan_png from inv_cards where rowid = ?', [img_id])
	r = cursor.fetchone()
	if r is None:
		return ("img not found", 404)
	else:
		return send_file(StringIO(r[0]), 'image/png')

@app.route('/known_image/<set_abbrev>/<name>')
def known_image(set_abbrev,name):
	base_dir = '/home/talin/Cockatrice/cards/downloadedPics' #'' #YOUR BASE_DIR HERE
	sub_path = os.path.join(set_abbrev,name+'.full.jpg')
	path = safe_join(base_dir, sub_path)
	if os.path.exists(path):
		img = cv.LoadImage(path.encode('utf-8'), 0)
		return send_file(StringIO(cv.EncodeImage('.PNG',img).tostring()), 'image/png')
	else:
		return ("img not found", 404)


@app.route('/search')
def search():
	page_size = 10;
	connection = sqlite3.connect('inventory.sqlite3')
	cursor = connection.cursor()
	cols = ['rowid', 'name', 'set_name', 'box', 'box_index', 'recognition_status']
	where_clause = ""
	where_params = []
	for key in cols:
		val = request.args.get(key)
		if val is not None:
			if len(where_params) == 0:
				where_clause = " where "
			else:
				where_clause += " and "
			where_clause += (key + " = ?")
			where_params.append(val)
	query = "select %s from inv_cards" % ", ".join(cols)
	query += where_clause
	
	page_num = 0
	val = request.args.get("page")
	if val is not None: 
		page_num = int(val)-1
	query += " limit ? offset ?";

	print query
	print page_num * page_size
	cursor.execute(query, where_params+[page_size, page_num*page_size])
	results = [dict(zip(cols,r)) for r in cursor.fetchall()]
	return render_template('results.html', cards=results)

@app.route('/verify_scans', methods=['POST', 'GET'])
def verify_scans():
	if request.method == 'POST':
		#split_names = [name.split('_',1) + [val] for name,val in request.form]
		split_names = [name.split('_',1) + [val] for name,val in request.form.items()]
		by_rid = lambda (rid,x,y): rid
		d = {}
		for rid, args in  groupby(sorted(split_names, key=by_rid), by_rid):
			d[rid] = dict([a[1:] for a in list(args)])

		for rid, attribs in d.items():
			card = InvCard.query.filter_by(rowid=rid).one()
			if card.name != attribs['name'] or card.set_name != attribs['set_name']:
				FixLog(
						card = card,
						orig_set = card.set_name,
						orig_name = card.name,
						new_set = attribs['set_name'],
						new_name = attribs['name'],
						scan_png = card.scan_png
				)
				card.name = attribs['name']
				card.set_name = attribs['set_name']

			card.recognition_status = 'verified'
			session.commit()

	results = InvCard.query.filter_by(recognition_status='candidate_match').order_by('name').limit(50).all()
	return render_template('verify.html', cards=results)


if __name__ == '__main__':
	app.run(debug=True)
