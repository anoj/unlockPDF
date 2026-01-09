from flask import Blueprint, render_template, request, jsonify
import json
import re
import xml.dom.minidom as minidom
import cssbeautifier
import jsbeautifier
from bs4 import BeautifulSoup

unminify_bp = Blueprint('unminify', __name__, url_prefix='/unminify')


@unminify_bp.route('/')
def unminify_index():
    return render_template('unminify.html')


class Unminifier:
    def __init__(self):
        self.js_options = {
            'indent_size': 2,
            'indent_char': ' ',
            'max_preserve_newlines': 2,
            'preserve_newlines': True,
            'end_with_newline': True
        }

        self.css_options = {
            'indent_size': 2,
            'indent_char': ' ',
            'end_with_newline': True
        }

    def unminify_js(self, code):
        return jsbeautifier.beautify(code, self.js_options)

    def unminify_css(self, code):
        return cssbeautifier.beautify(code, self.css_options)

    def unminify_html(self, code):
        soup = BeautifulSoup(code, 'html.parser')
        return soup.prettify()

    def unminify_json(self, code):
        parsed = json.loads(code)
        return json.dumps(parsed, indent=2, ensure_ascii=False)

    def unminify_xml(self, code):
        dom = minidom.parseString(code)
        pretty_xml = dom.toprettyxml(indent="  ")

        lines = [l for l in pretty_xml.split("\n") if l.strip()]
        if lines[0].startswith("<?xml"):
            lines = lines[1:]

        return "\n".join(lines)

    def detect_type(self, code):
        code = code.strip()

        try:
            json.loads(code)
            return "json"
        except:
            pass

        try:
            minidom.parseString(code)
            return "xml"
        except:
            pass

        if "<html" in code.lower():
            return "html"

        if re.search(r"[.#][\w-]+\s*{", code):
            return "css"

        return "js"

    def unminify(self, code, code_type=None):
        if not code:
            raise ValueError("No code provided")

        if not code_type:
            code_type = self.detect_type(code)

        if code_type == "js":
            return self.unminify_js(code)
        if code_type == "css":
            return self.unminify_css(code)
        if code_type == "html":
            return self.unminify_html(code)
        if code_type == "json":
            return self.unminify_json(code)
        if code_type == "xml":
            return self.unminify_xml(code)

        raise ValueError("Unsupported type")


unminifier = Unminifier()

# ===============================
# API ENDPOINT
# ===============================

@unminify_bp.route('/process', methods=['POST'])
def unminify_process():
    try:
        data = request.get_json()

        code = data.get("code")
        code_type = data.get("type")  # optional

        result = unminifier.unminify(code, code_type)

        return jsonify({
            "success": True,          # ✅ frontend expects this
            "type": code_type or unminifier.detect_type(code),
            "result": result          # ✅ frontend expects this
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
# ===============================
