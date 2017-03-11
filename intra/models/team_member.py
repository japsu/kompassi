# encoding: utf-8

from __future__ import unicode_literals

import logging

from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from core.utils import ensure_user_is_member_of_group, pick_attrs
from core.models.constants import NAME_DISPLAY_STYLE_CHOICES


NAME_DISPLAY_STYLE_CHOICES = [
    ('', _('As set by the user themself')),
] + NAME_DISPLAY_STYLE_CHOICES


logger = logging.getLogger('kompassi')


@python_2_unicode_compatible
class TeamMember(models.Model):
    team = models.ForeignKey('intra.Team', related_name='members')
    person = models.ForeignKey('core.Person', related_name='team_memberships')

    is_primary_team = models.BooleanField(
        default=True,
        verbose_name=_('Default team'),
        help_text=_('In some listings where space is tight, the person is only shown under their default team. Designating one team as the default for someone replaces their prior default team.'),
    )
    is_team_leader = models.BooleanField(
        default=False,
        verbose_name=_('Team leader'),
        help_text=_('Team leaders are placed first and hilighted in listings.'),
    )
    is_shown_internally = models.BooleanField(
        default=True,
        verbose_name=_('Display internally'),
        help_text=_('Controls whether this person is shown in internal listings. You might want to un-tick this for people who have been added to this team for only the access or mailing lists.'),
    )
    is_shown_publicly = models.BooleanField(
        default=True,
        verbose_name=_('Display publicly'),
        help_text=_('Controls whether this person is shown in public listings.'),
    )
    is_group_member = models.BooleanField(
        default=True,
        verbose_name=_('Group membership'),
        help_text=_('Controls whether this person is added to the user group of this team. Group membership in turn usually controls membership on mailing lists and may convey additional access privileges.'),
    )
    override_name_display_style = models.CharField(
        max_length=max(len(key) for (key, label) in NAME_DISPLAY_STYLE_CHOICES),
        blank=True,
        choices=NAME_DISPLAY_STYLE_CHOICES,
        default='',
        verbose_name=_('Override name display style'),
        help_text=_('For the purpose of public listings, the name display style of the team member may be overridden here.'),
    )

    @property
    def event(self):
        return self.team.event if self.team else None

    @property
    def signup(self):
        from labour.models import Signup
        return Signup.objects.get(event=self.event, person=self.person)

    def admin_get_event(self):
        return self.event
    admin_get_event.short_description = _('Event')
    admin_get_event.admin_order_field = 'team__event'

    @property
    def css_classes(self):
        classes = []

        if self.is_team_leader:
            classes.append('kompassi-intra-team-leader')

        if not self.is_shown_internally:
            classes.append('text-muted')

        return ' '.join(classes)

    def __str__(self):
        return self.person.full_name if self.person else 'None'

    @classmethod
    def get_or_create_dummy(cls):
        from core.models import Person
        from .team import Team

        team, unused = Team.get_or_create_dummy()
        person, unused = Person.get_or_create_dummy()

        return cls.objects.get_or_create(
            team=team,
            person=person,
        )

    @property
    def display_name(self):
        if self.override_name_display_style:
            return self.person.get_formatted_name(self.override_name_display_style)
        else:
            return self.person.display_name

    def as_dict(self):
        return pick_attrs(self,
            'is_team_leader',
            'display_name',

            email=self.signup.email_address,
            job_title=self.signup.job_title,
        )

    class Meta:
        verbose_name = _('Team member')
        verbose_name_plural = _('Team members')
        unique_together = [('team', 'person')]
        ordering = ('team', '-is_team_leader', 'person__surname', 'person__first_name')


@receiver(post_save, sender=TeamMember)
def on_team_member_update(sender, instance, **kwargs):
    logger.debug('TeamMember %s update hook', instance)

    # only one primary team per person per event
    if instance.is_primary_team:
        TeamMember.objects.filter(
            team__event=instance.event,
            person=instance.person,
            is_primary_team=True,
        ).exclude(
            id=instance.id,
        ).update(
            is_primary_team=False
        )

    ensure_user_is_member_of_group(instance.person.user, instance.team.group, instance.is_group_member)

@receiver(post_delete, sender=TeamMember)
def on_team_member_delete(sender, instance, **kwargs):
    logger.debug('TeamMember %s delete hook', instance)
    ensure_user_is_member_of_group(instance.person.user, instance.team.group, False)
