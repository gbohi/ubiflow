"""Journal d'activité : une ligne par opération significative (en ajout seul)."""
from .models import JournalActivite


def infos_requete(request):
    """Adresse IP, navigateur / application et canal (en-tête X-Canal : web | mobile)."""
    if request is None:
        return {}
    ip = (request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR') or '').split(',')[0].strip()
    canal = (request.META.get('HTTP_X_CANAL') or 'web').lower()[:10]
    return {'adresse_ip': ip or None, 'agent': (request.META.get('HTTP_USER_AGENT') or '')[:255],
            'canal': canal if canal in ('web', 'mobile') else 'web'}


def journaliser(auteur, action, objet=None, *, objet_type='', objet_id='', libelle='', avant=None, apres=None,
                motif='', request=None, pour_compte_de=None):
    if objet is not None:
        objet_type = objet_type or objet._meta.label
        objet_id = objet_id or str(objet.pk)
        libelle = libelle or str(objet)[:255]
    return JournalActivite.objects.create(
        auteur=auteur if getattr(auteur, 'is_authenticated', False) else None,
        pour_compte_de=pour_compte_de, action=action, objet_type=objet_type, objet_id=str(objet_id),
        objet_libelle=libelle[:255], avant=avant, apres=apres, motif=motif or '', **infos_requete(request))
