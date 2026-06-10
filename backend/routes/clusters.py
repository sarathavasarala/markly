"""Flask blueprint route handlers for Radar Clusters."""
from __future__ import annotations

import logging
from flask import Blueprint, g, jsonify, request

from database import get_db, rows_to_dicts, row_to_dict
from middleware.auth import require_auth
from services import clustering

logger = logging.getLogger(__name__)

clusters_bp = Blueprint("clusters", __name__)


@clusters_bp.route("", methods=["GET"])
@require_auth
def list_clusters():
    """Get all active clusters for the current user."""
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT c.*,
                   (SELECT COUNT(*)
                    FROM signal_cluster_items sci
                    WHERE sci.cluster_id = c.id
                      AND (c.last_report_generated_at IS NULL OR datetime(sci.added_at) > datetime(c.last_report_generated_at))
                   ) AS new_since_last_report
            FROM signal_clusters c
            WHERE c.user_id = ? AND c.status = 'active'
            ORDER BY c.last_seen_at DESC
            """,
            (g.user.id,)
        ).fetchall()
        
        clusters = rows_to_dicts(rows)
        
        for cl in clusters:
            item_rows = conn.execute(
                """
                SELECT i.id, i.feed_id, i.url, i.title, i.summary, i.status, i.published_at, i.first_seen_at, i.bookmark_id,
                       f.title AS feed_title, f.site_url AS feed_site_url, f.favicon_url AS feed_favicon_url,
                       b.thumbnail_url AS bookmark_thumbnail_url
                FROM feed_items i
                JOIN feeds f ON f.id = i.feed_id AND f.user_id = i.user_id
                JOIN signal_cluster_items sci ON sci.feed_item_id = i.id
                LEFT JOIN bookmarks b ON b.id = i.bookmark_id
                WHERE sci.cluster_id = ?
                ORDER BY COALESCE(i.published_at, i.first_seen_at) DESC
                """,
                (cl["id"],)
            ).fetchall()
            cl["items"] = rows_to_dicts(item_rows)
            
            report_row = conn.execute(
                "SELECT * FROM signal_cluster_reports WHERE cluster_id = ? ORDER BY generated_at DESC LIMIT 1",
                (cl["id"],)
            ).fetchone()
            cl["latest_report"] = row_to_dict(report_row)
            
        return jsonify({"clusters": clusters}), 200
    except Exception as exc:
        logger.exception("Failed to list clusters")
        return jsonify({"error": f"Failed to list clusters: {str(exc)}"}), 500


@clusters_bp.route("/refresh", methods=["POST"])
@require_auth
def refresh_clusters():
    """Run clustering process for the user's recent RSS feed items."""
    try:
        stats = clustering.refresh_clusters(g.user.id)
        
        # Reload the active clusters list to return to the frontend
        conn = get_db()
        rows = conn.execute(
            """
            SELECT c.*,
                   (SELECT COUNT(*)
                    FROM signal_cluster_items sci
                    WHERE sci.cluster_id = c.id
                      AND (c.last_report_generated_at IS NULL OR datetime(sci.added_at) > datetime(c.last_report_generated_at))
                   ) AS new_since_last_report
            FROM signal_clusters c
            WHERE c.user_id = ? AND c.status = 'active'
            ORDER BY c.last_seen_at DESC
            """,
            (g.user.id,)
        ).fetchall()
        clusters = rows_to_dicts(rows)
        
        return jsonify({
            "clusters": clusters,
            "created": stats["created"],
            "updated": stats["updated"],
            "archived": stats["archived"]
        }), 200
    except Exception as exc:
        logger.exception("Failed to refresh clusters")
        return jsonify({"error": f"Failed to refresh clusters: {str(exc)}"}), 500


@clusters_bp.route("/<cluster_id>", methods=["GET"])
@require_auth
def get_cluster(cluster_id: str):
    """Get detailed cluster information including feed items and latest report."""
    conn = get_db()
    try:
        # Load cluster row
        cluster_row = conn.execute(
            "SELECT * FROM signal_clusters WHERE id = ? AND user_id = ?",
            (cluster_id, g.user.id)
        ).fetchone()
        
        if not cluster_row:
            return jsonify({"error": "Cluster not found"}), 404
            
        cluster = row_to_dict(cluster_row)
        
        # Include new_since_last_report count in detail too
        new_items_row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM signal_cluster_items
            WHERE cluster_id = ?
              AND (? IS NULL OR datetime(added_at) > datetime(?))
            """,
            (cluster_id, cluster["last_report_generated_at"], cluster["last_report_generated_at"])
        ).fetchone()
        cluster["new_since_last_report"] = new_items_row["count"] if new_items_row else 0
        
        # Load associated feed items
        item_rows = conn.execute(
            """
            SELECT i.id, i.feed_id, i.guid, i.url, i.title, i.author, i.published_at, i.summary,
                   i.content, i.content_format, i.status, i.bookmark_id, i.first_seen_at, i.updated_at,
                   f.title AS feed_title, f.site_url AS feed_site_url, f.favicon_url AS feed_favicon_url,
                   b.thumbnail_url AS bookmark_thumbnail_url
            FROM feed_items i
            JOIN feeds f ON f.id = i.feed_id AND f.user_id = i.user_id
            JOIN signal_cluster_items sci ON sci.feed_item_id = i.id
            LEFT JOIN bookmarks b ON b.id = i.bookmark_id
            WHERE sci.cluster_id = ?
            ORDER BY COALESCE(i.published_at, i.first_seen_at) DESC
            """,
            (cluster_id,)
        ).fetchall()
        items = rows_to_dicts(item_rows)
        
        # Load latest generated report
        report_row = conn.execute(
            "SELECT * FROM signal_cluster_reports WHERE cluster_id = ? ORDER BY generated_at DESC LIMIT 1",
            (cluster_id,)
        ).fetchone()
        latest_report = row_to_dict(report_row)
        
        # Combine
        cluster["items"] = items
        cluster["latest_report"] = latest_report
        
        return jsonify(cluster), 200
    except Exception as exc:
        logger.exception(f"Failed to get cluster details for {cluster_id}")
        return jsonify({"error": f"Failed to get cluster details: {str(exc)}"}), 500


@clusters_bp.route("/<cluster_id>/reports", methods=["GET"])
@require_auth
def list_reports(cluster_id: str):
    """List all reports generated for the cluster."""
    conn = get_db()
    try:
        # Verify ownership
        cluster_row = conn.execute(
            "SELECT id FROM signal_clusters WHERE id = ? AND user_id = ?",
            (cluster_id, g.user.id)
        ).fetchone()
        
        if not cluster_row:
            return jsonify({"error": "Cluster not found"}), 404
            
        rows = conn.execute(
            "SELECT * FROM signal_cluster_reports WHERE cluster_id = ? ORDER BY generated_at DESC",
            (cluster_id,)
        ).fetchall()
        
        reports = rows_to_dicts(rows)
        return jsonify({"reports": reports}), 200
    except Exception as exc:
        logger.exception(f"Failed to list reports for cluster {cluster_id}")
        return jsonify({"error": f"Failed to list reports: {str(exc)}"}), 500


@clusters_bp.route("/<cluster_id>/reports/generate", methods=["POST"])
@require_auth
def generate_report(cluster_id: str):
    """Generate a new intelligence report from the cluster articles."""
    try:
        report = clustering.generate_cluster_report(g.user.id, cluster_id)
        return jsonify(report), 201
    except ValueError as val_err:
        logger.warning(f"Validation failure in report generation: {val_err}")
        return jsonify({"error": str(val_err)}), 400
    except Exception as exc:
        logger.exception(f"Failed to generate report for cluster {cluster_id}")
        return jsonify({"error": f"Failed to generate report: {str(exc)}"}), 500


@clusters_bp.route("/<cluster_id>", methods=["DELETE"])
@require_auth
def delete_cluster(cluster_id: str):
    """Delete the cluster (and its reports/items via cascade delete)."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id FROM signal_clusters WHERE id = ? AND user_id = ?",
            (cluster_id, g.user.id)
        ).fetchone()
        
        if not row:
            return jsonify({"error": "Cluster not found"}), 404
            
        conn.execute("DELETE FROM signal_clusters WHERE id = ?", (cluster_id,))
        conn.commit()
        
        return jsonify({"success": True}), 200
    except Exception as exc:
        logger.exception(f"Failed to delete cluster {cluster_id}")
        return jsonify({"error": f"Failed to delete cluster: {str(exc)}"}), 500
