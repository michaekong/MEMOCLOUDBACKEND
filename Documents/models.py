from django.db import models

class Cni(models.Model):
    recto = models.ImageField(upload_to="cni/")
    verso = models.ImageField(upload_to="cni/")

class TitreFoncier(models.Model):
    doc = models.FileField(upload_to="titres/")

class PlanCadastral(models.Model):
    doc = models.FileField(upload_to="plans/")

class CertificatHypotheque(models.Model):
    doc = models.FileField(upload_to="hypotheques/")

