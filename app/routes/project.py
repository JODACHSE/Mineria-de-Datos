from flask import Blueprint, render_template

project_bp = Blueprint('project', __name__)

@project_bp.route('/')
def index():
    return render_template('project/index.html')