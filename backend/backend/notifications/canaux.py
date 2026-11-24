"""
Canaux de notification (§11) : l'application reçoit toujours la notification ;
l'e-mail (SMTP de la société) et le push mobile (Firebase) s'y ajoutent selon
l'événement, les préférences du collaborateur et l'activation des canaux.
Les envois partent après la validation de la transaction (jamais pour une action annulée).
"""
import json
import logging
from html import escape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)

# code : (libellé, e-mail par défaut, push par défaut, désactivable)
EVENEMENTS = {
    'validation_attendue': ('Validation attendue', True, True, False),
    'rappel': ('Rappel de validation en attente', True, True, False),
    'escalade': ('Escalade d\'une validation en retard', True, True, True),
    'demande_soumise': ('Accusé de soumission', False, False, True),
    'validation_effectuee': ('Étape validée', False, False, True),
    'demande_approuvee': ('Demande approuvée', True, True, True),
    'demande_rejetee': ('Demande rejetée', True, True, True),
    'demande_retournee': ('Demande retournée pour correction', True, True, True),
    'demande_annulee': ('Demande annulée', False, True, True),
    'commentaire': ('Nouveau commentaire', False, True, True),
    'correction': ('Montant ou contenu corrigé', True, False, True),
    'a_payer': ('Demande à payer (comptabilité)', False, False, True),
    'paiement': ('Paiement effectué', False, True, True),
    'reversement': ('Reversement à effectuer ou reçu', True, False, True),
    'cloture': ('Clôture de mission (validée, retournée, dépassement)', True, True, True),
    'rappel_cloture': ('Rappel : clôture de mission attendue', True, True, True),
    'cloture_a_controler': ('Clôture à contrôler', True, False, True),
    'delegation_recue': ('Délégation reçue', True, False, True),
    'delegation_revoquee': ('Délégation révoquée', False, False, True),
    'workflow_bloque': ('Soumission bloquée par le paramétrage', True, False, True),
    'workflow_a_reaffecter': ('Validation à réaffecter', True, False, True),
}


def email_configure():
    from api.models import ParametreSysteme
    return bool(getattr(settings, 'EMAIL_HOST', '')) and ParametreSysteme.charger().canal_email


def push_configure():
    from api.models import ParametreSysteme
    return bool(getattr(settings, 'FIREBASE_CREDENTIALS', '')) and ParametreSysteme.charger().canal_push


def canaux_de(user, evenement, prefs=None):
    """(email, push) pour cet événement : préférence du collaborateur, sinon valeur par défaut."""
    libelle, email, push, desactivable = EVENEMENTS.get(evenement, (evenement, False, False, True))
    if desactivable:
        p = prefs.get(evenement) if prefs is not None else user.preferences_notification.filter(evenement=evenement).first()
        if p is not None:
            email, push = (p['email'], p['push']) if isinstance(p, dict) else (p.email, p.push)
    return email, push


def _lien_absolu(lien):
    base = getattr(settings, 'FRONTEND_URL', '') or ''
    return f"{base.rstrip('/')}{lien}" if base and lien else ''


def envoyer_email(notification):
    u = notification.destinataire
    if not u.email:
        return False
    lien = _lien_absolu(notification.lien)
    texte = f"{notification.message}\n\n{('Ouvrir dans UbiFlow : ' + lien) if lien else ''}\n\n— UbiFlow"
    bouton = (f'<p><a href="{escape(lien)}" style="background:#0F3A6E;color:#fff;padding:9px 16px;border-radius:6px;'
              f'text-decoration:none;display:inline-block">Ouvrir dans UbiFlow</a></p>') if lien else ''
    html = (f'<div style="font-family:Arial,sans-serif;color:#1f2d3d;max-width:560px">'
            f'<p style="font-size:18px;font-weight:bold;color:#092440;margin:0 0 4px">Ubi<span style="color:#2FB46C">Flow</span></p>'
            f'<h2 style="font-size:16px;margin:16px 0 8px">{escape(notification.titre)}</h2>'
            f'<p style="white-space:pre-line">{escape(notification.message)}</p>{bouton}'
            f'<p style="font-size:11px;color:#5A7090;margin-top:24px">Vous recevez ce message selon vos préférences de '
            f'notification (UbiFlow → Préférences).</p></div>')
    m = EmailMultiAlternatives(f"[UbiFlow] {notification.titre}", texte, settings.DEFAULT_FROM_EMAIL, [u.email])
    m.attach_alternative(html, 'text/html')
    m.send()
    return True


def _jeton_firebase():
    """Jeton OAuth du compte de service Firebase (google-auth), mis en cache par la bibliothèque."""
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    if not hasattr(_jeton_firebase, 'credentials'):
        _jeton_firebase.credentials = service_account.Credentials.from_service_account_file(
            settings.FIREBASE_CREDENTIALS, scopes=['https://www.googleapis.com/auth/firebase.messaging'])
    c = _jeton_firebase.credentials
    if not c.valid:
        c.refresh(Request())
    return c.token, c.project_id


def envoyer_push(notification):
    import requests
    from .models import AppareilMobile
    appareils = list(AppareilMobile.objects.filter(user=notification.destinataire, actif=True))
    if not appareils:
        return 0
    jeton, projet = _jeton_firebase()
    n = 0
    for a in appareils:
        corps = {'message': {'token': a.jeton, 'notification': {'title': notification.titre, 'body': notification.message[:240]},
                             'data': {'lien': notification.lien or '', 'demande': str(notification.demande_id or '')}}}
        r = requests.post(f"https://fcm.googleapis.com/v1/projects/{projet}/messages:send", timeout=10,
                          headers={'Authorization': f'Bearer {jeton}', 'Content-Type': 'application/json'}, data=json.dumps(corps))
        if r.status_code == 404 or (r.status_code == 400 and 'UNREGISTERED' in r.text):
            a.actif = False  # application désinstallée ou jeton expiré
            a.save(update_fields=['actif'])
        elif r.ok:
            n += 1
        else:
            logger.warning("Push refusé (%s) : %s", r.status_code, r.text[:200])
    return n


def diffuser(ids):
    """E-mail et push des notifications créées (appelé après la validation de la transaction)."""
    from .models import Notification, PreferenceNotification
    email_ok, push_ok = email_configure(), push_configure()
    if not (email_ok or push_ok):
        return
    notifs = list(Notification.objects.filter(pk__in=ids).select_related('destinataire'))
    prefs = {}
    for p in PreferenceNotification.objects.filter(user__in=[n.destinataire_id for n in notifs]).values('user_id', 'evenement', 'email', 'push'):
        prefs.setdefault(p['user_id'], {})[p['evenement']] = p
    for n in notifs:
        email, push = canaux_de(n.destinataire, n.evenement, prefs.get(n.destinataire_id, {}))
        try:
            if email and email_ok:
                envoyer_email(n)
            if push and push_ok:
                envoyer_push(n)
        except Exception:  # un canal en panne ne doit jamais bloquer l'application
            logger.exception("Envoi de la notification %s impossible", n.pk)
