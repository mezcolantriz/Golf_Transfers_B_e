from flask import Blueprint, jsonify

transfers_bp = Blueprint('transfers', __name__)

@transfers_bp.route('/api/transfer-time', methods=['GET'])
def get_transfer_time():
    return jsonify({"message": "Transfer time calculation endpoint"})
