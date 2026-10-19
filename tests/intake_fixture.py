"""Explicitly skipped interview for legacy plan lifecycle tests.

Those tests exercise revisions/check-ins/recipes, not initial readiness. New
interview tests start with a fresh workspace and exercise the gate separately.
"""
import intake
import product
import server

def skipped_interview(conversation):
    w=product.workspace(server)
    w['interview']={'skipped':list(intake.QUESTIONS)}
    w['sessions'][conversation]={'today_context_date':product.today(),'today_context':'尚未进食，接下来正常吃饭'}
    server.save_json(server.DATA/'workspace.json',w)
