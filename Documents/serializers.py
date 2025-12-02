from rest_framework import serializers
from .models import Cni, TitreFoncier, PlanCadastral, CertificatHypotheque

class CniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cni
        fields = "__all__"

class TitreFoncierSerializer(serializers.ModelSerializer):
    class Meta:
        model = TitreFoncier
        fields = "__all__"

class PlanCadastralSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanCadastral
        fields = "__all__"

class CertificatHypothequeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CertificatHypotheque
        fields = "__all__"
