from flask import Blueprint, render_template

lessons_bp = Blueprint('lessons', __name__)

@lessons_bp.route('/')
def index():
    return render_template('lessons/index.html')

@lessons_bp.route('/clase-01')
def clase_01():
    return render_template('lessons/clase_01.html')