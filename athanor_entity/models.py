from django.db import models
from evennia.typeclasses.models import SharedMemoryModel


class StructureBridge(SharedMemoryModel):
    db_object = models.OneToOneField('objects.ObjectDB', related_name='structure_bridge', primary_key=True,
                                     on_delete=models.CASCADE)
    db_name = models.CharField(max_length=255, null=False, blank=False)
    db_iname = models.CharField(max_length=255, null=False, blank=False)
    db_cname = models.CharField(max_length=255, null=False, blank=False)
    db_structure_path = models.CharField(max_length=255, null=False, blank=False)
    db_system_identifier = models.CharField(max_length=255, null=True, blank=False, unique=True)


class RegionBridge(models.Model):
    object = models.OneToOneField('objects.ObjectDB', related_name='region_bridge', primary_key=True,
                                  on_delete=models.CASCADE)
    system_key = models.CharField(max_length=255, blank=False, null=False, unique=True)


class MapBridge(models.Model):
    object = models.OneToOneField('objects.ObjectDB', related_name='map_bridge', primary_key=True,
                                     on_delete=models.CASCADE)
    plugin = models.CharField(max_length=255, null=False, blank=False)
    map_key = models.CharField(max_length=255, null=False, blank=False)


class GameLocations(models.Model):
    object = models.ForeignKey('objects.ObjectDB', related_name='saved_locations', on_delete=models.CASCADE)
    name = models.CharField(max_length=255, null=False, blank=False)
    map = models.ForeignKey('objects.ObjectDB', related_name='objects_here', on_delete=models.CASCADE)
    room_key = models.CharField(max_length=255, null=False, blank=False)
    x_coordinate = models.FloatField(null=True)
    y_coordinate = models.FloatField(null=True)
    z_coordinate = models.FloatField(null=True)

    class Meta:
        unique_together = (('object', 'name'),)


