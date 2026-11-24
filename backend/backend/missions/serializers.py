from rest_framework import serializers

from .models import Distance, LigneCalcul, Pays, Ville


class PaysSerializer(serializers.ModelSerializer):
    nb_villes = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Pays
        fields = '__all__'

    def validate_code_iso(self, v):
        v = (v or '').strip().upper()
        if len(v) != 2 or not v.isalpha():
            raise serializers.ValidationError('Code ISO sur 2 lettres (ex. CI, FR).')
        return v

    def validate_devise_usuelle(self, v):
        return (v or '').strip().upper()


class VilleSerializer(serializers.ModelSerializer):
    pays_libelle = serializers.ReadOnlyField(source='pays.libelle')
    pays_code = serializers.ReadOnlyField(source='pays.code_iso')

    class Meta:
        model = Ville
        fields = '__all__'
        validators = []

    def validate(self, attrs):
        libelle = attrs.get('libelle', getattr(self.instance, 'libelle', '')).strip()
        pays = attrs.get('pays', getattr(self.instance, 'pays', None))
        doublon = Ville.objects.filter(libelle__iexact=libelle, pays=pays)
        if self.instance is not None:
            doublon = doublon.exclude(pk=self.instance.pk)
        if doublon.exists():
            raise serializers.ValidationError({'libelle': 'Cette ville existe déjà pour ce pays.'})
        attrs['libelle'] = libelle
        return attrs


class DistanceSerializer(serializers.ModelSerializer):
    ville_a_libelle = serializers.ReadOnlyField(source='ville_a.libelle')
    ville_b_libelle = serializers.ReadOnlyField(source='ville_b.libelle')

    class Meta:
        model = Distance
        fields = '__all__'
        validators = []

    def validate(self, attrs):
        a = attrs.get('ville_a', getattr(self.instance, 'ville_a', None))
        b = attrs.get('ville_b', getattr(self.instance, 'ville_b', None))
        if a == b:
            raise serializers.ValidationError({'ville_b': 'Choisissez deux villes différentes.'})
        if a.pays_id != b.pays_id:
            raise serializers.ValidationError({'ville_b': 'Les distances concernent des villes du même pays.'})
        if attrs.get('km', getattr(self.instance, 'km', 0)) <= 0:
            raise serializers.ValidationError({'km': 'Distance positive attendue.'})
        existante = Distance.entre(a, b)
        if existante and (self.instance is None or existante.pk != self.instance.pk):
            raise serializers.ValidationError({'ville_b': 'La distance entre ces deux villes existe déjà.'})
        return attrs


class LigneCalculSerializer(serializers.ModelSerializer):
    rubrique_libelle = serializers.CharField(source='get_rubrique_display', read_only=True)

    class Meta:
        model = LigneCalcul
        exclude = ['demande']
