import datetime
import string
import random
from decimal import Decimal
from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from flask_login import login_required, current_user
from .. import db
from ..models import Angebote, Kaeufe, Nutzer, Betriebe, Arbeit, Arbeiter, Auszahlungen
from ..forms import ProductSearchForm
from ..tables import KaeufeTable, Preiszusammensetzung
from ..composition_of_prices import get_table_of_composition, get_positions_in_table, create_dots
from ..kauf_vorgang import kauf_vorgang
from sqlalchemy.sql import func



main_nutzer = Blueprint('main_nutzer', __name__, template_folder='templates',
    static_folder='static')


def id_generator(size=10, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.SystemRandom().choice(chars) for _ in range(size))


@main_nutzer.route('/nutzer/kaeufe')
@login_required
def meine_kaeufe():
    try:
        user_type = session["user_type"]
    except:
        user_type = "nutzer"

    if user_type == "betrieb":
        return redirect(url_for('auth.zurueck'))
    else:
        session["user_type"] = "nutzer"

        kaufhistorie = db.session.query(Kaeufe.id, Angebote.name, Angebote.beschreibung,\
            func.concat(func.round(Angebote.preis, 2), " Std.").label("preis")
            ).\
            select_from(Kaeufe).\
            filter_by(nutzer=current_user.id).\
            join(Angebote, Kaeufe.angebot==Angebote.id).all()
        kaufh_table = KaeufeTable(kaufhistorie, no_items="(Noch keine Käufe.)")
        return render_template('meine_kaeufe.html', kaufh_table=kaufh_table)


@main_nutzer.route('/nutzer/suchen', methods=['GET', 'POST'])
@login_required
def suchen():
    search = ProductSearchForm(request.form)
    # grouping by all kind of attributes of angebote, aggregating ID with min() --> only
    # 1 angebot of the same kind is shown.
    qry = db.session.query(func.min(Angebote.id).label("id"), Angebote.name.label("angebot_name"),\
        Betriebe.name.label("betrieb_name"), Betriebe.email,\
        Angebote.beschreibung, Angebote.kategorie, Angebote.preis,
        func.count(Angebote.id).label("vorhanden")).select_from(Angebote).\
        join(Betriebe, Angebote.betrieb==Betriebe.id).filter(Angebote.aktiv == True).\
        group_by(Angebote.cr_date, "angebot_name", "betrieb_name",
            Betriebe.email, Angebote.beschreibung, Angebote.kategorie, Angebote.preis)
    results = qry.all()

    if request.method == 'POST':
        results = []
        search_string = search.data['search']

        if search_string:
            if search.data['select'] == 'Name':
                results = qry.filter(Angebote.name.contains(search_string)).all()

            elif search.data['select'] == 'Beschreibung':
                results = qry.filter(Angebote.beschreibung.contains(search_string)).all()

            elif search.data['select'] == 'Kategorie':
                results = qry.filter(Angebote.kategorie.contains(search_string)).all()

            else:
                results = qry.all()
        else:
            results = qry.all()

        if not results:
            flash('Keine Ergebnisse!')
            return redirect('/nutzer/suchen')
        else:
            return render_template('suchen_nutzer.html', form=search, results=results)

    return render_template('suchen_nutzer.html', form=search, results=results)


@main_nutzer.route('/nutzer/details/<int:id>', methods=['GET', 'POST'])
def details(id):

    table_of_composition =  get_table_of_composition(id)
    cols_dict = get_positions_in_table(table_of_composition)
    dot = create_dots(cols_dict, table_of_composition)
    piped = dot.pipe().decode('utf-8')
    table_preiszus = Preiszusammensetzung(table_of_composition)

    if request.method == 'POST':
        return redirect('/nutzer/suchen')

    return render_template('details_nutzer.html', table_preiszus=table_preiszus, piped=piped)


@main_nutzer.route('/nutzer/kaufen/<int:id>', methods=['GET', 'POST'])
def kaufen(id):
    qry = db.session.query(Angebote).filter(
                Angebote.id==id)
    angebot = qry.first()
    if angebot:
        if request.method == 'POST':
            kauf_vorgang(kaufender_type="nutzer", angebot=angebot, kaeufer_id=current_user.id)
            flash(f"Kauf von '{angebot.name}' erfolgreich!")
            return redirect('/nutzer/suchen')

        return render_template('kaufen_nutzer.html', angebot=angebot)
    else:
        return 'Error loading #{id}'.format(id=id)


@main_nutzer.route('/nutzer/profile')
@login_required
def profile():
    user_type = session["user_type"]
    if user_type == "nutzer":
        arbeitsstellen = db.session.query(Betriebe).select_from(Arbeiter).\
            filter_by(nutzer=current_user.id).join(Betriebe, Arbeiter.betrieb==Betriebe.id).all()

        return render_template('profile_nutzer.html', arbeitsstellen=arbeitsstellen)
    elif user_type == "betrieb":
        return redirect(url_for('auth.zurueck'))

@main_nutzer.route('/nutzer/auszahlung', methods=['GET', 'POST'])
@login_required
def auszahlung():
    if request.method == 'POST':

        betrag = Decimal(request.form["betrag"])
        code = id_generator()

        # neuer eintrag in db-table auszahlungen
        neue_auszahlung = Auszahlungen(type_nutzer=True, nutzer=current_user.id, betrag=betrag, code=code)
        db.session.add(neue_auszahlung)
        db.session.commit()

        # betrag vom guthaben des users abziehen
        nutzer = db.session.query(Nutzer).filter(Nutzer.id == current_user.id).first()
        nutzer.guthaben -= betrag
        db.session.commit()

        # Code User anzeigen
        flash(betrag)
        flash(code)

        # Einlösen des Codes auch hier ermöglichen

        return render_template('auszahlung_nutzer.html')

    return render_template('auszahlung_nutzer.html')

@main_nutzer.route('/nutzer/hilfe')
@login_required
def hilfe():
    return render_template('nutzer_hilfe.html')
