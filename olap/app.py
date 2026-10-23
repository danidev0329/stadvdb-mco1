"""Flask web backend for the OLAP dashboard.

Run wth
'python -m olap.app'         
"""
from __future__ import annotations
import json
import decimal
import datetime
from flask import Flask, request, jsonify, render_template
import mysql.connector
from etl import config
from olap import queries

app = Flask(__name__)




class _Encoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return int(o) if o == int(o) else float(o)
        if isinstance(o, (datetime.date, datetime.datetime)):
            return o.isoformat()
        return super().default(o)

app.json.encoder = _Encoder      # Flask 2.x+
app.config["JSON_SORT_KEYS"] = False




def _conn():
    return mysql.connector.connect(database=config.WAREHOUSE_DB, **config.MYSQL)


def _safe(fn):
    
    try:
        conn = _conn()
        rows = fn(conn)
        conn.close()
        return jsonify(rows)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500



@app.route("/")
def index():
    return render_template("index.html")




@app.route("/api/filters")
def filters():
    try:
        conn = _conn()
        result = {
            "years":         queries.distinct_values(conn, "year"),
            "quarters":      queries.distinct_values(conn, "quarter"),
            "couriers":      queries.distinct_values(conn, "courier"),
            "genders":       queries.distinct_values(conn, "gender"),
            "cities":        queries.distinct_values(conn, "city"),
            "vehicle_types": queries.distinct_values(conn, "vehicle_type"),
        }
        conn.close()
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500




@app.route("/api/rollup")
def api_rollup():
    granularity = request.args.get("granularity", "month")
    year        = request.args.get("year", type=int)
    courier     = request.args.get("courier")
    return _safe(lambda c: queries.rollup(c, granularity=granularity,
                                          year=year, courier=courier))


@app.route("/api/drilldown")
def api_drilldown():
    year    = request.args.get("year",    type=int)
    quarter = request.args.get("quarter", type=int)
    month   = request.args.get("month",   type=int)
    courier = request.args.get("courier")
    if year is None:
        return jsonify({"error": "year is required"}), 400
    return _safe(lambda c: queries.drilldown(c, year=year, quarter=quarter,
                                             month=month, courier=courier))


@app.route("/api/slice")
def api_slice():
    dimension = request.args.get("dimension")
    value     = request.args.get("value")
    gran      = request.args.get("granularity", "month")
    if not dimension or not value:
        return jsonify({"error": "dimension and value are required"}), 400
    return _safe(lambda c: queries.slice_query(c, dimension=dimension,
                                               value=value, granularity=gran))


@app.route("/api/dice")
def api_dice():
    return _safe(lambda c: queries.dice_query(
        c,
        year_start   = request.args.get("year_start",   type=int),
        year_end     = request.args.get("year_end",     type=int),
        courier      = request.args.get("courier"),
        gender       = request.args.get("gender"),
        city         = request.args.get("city"),
        vehicle_type = request.args.get("vehicle_type"),
        granularity  = request.args.get("granularity", "month"),
    ))


@app.route("/api/pivot")
def api_pivot():
    return _safe(lambda c: queries.pivot(
        c,
        granularity = request.args.get("granularity", "year"),
        year_start  = request.args.get("year_start", type=int),
        year_end    = request.args.get("year_end",   type=int),
    ))



if __name__ == "__main__":
    app.run(debug=True, port=5000)
