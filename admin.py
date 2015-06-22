"""Module that supports admin emails for subscriptions."""

import email
import logging
import webapp2
import yaml

from google.appengine.api import mail
from google.appengine.ext.webapp.mail_handlers import InboundMailHandler
from google.appengine.api import app_identity

import model

class AdminHandler(InboundMailHandler):
    """Handler for subscription requests by admin."""
    
    with open('config.yaml', 'r') as f:
        doc = yaml.load(f);
    
    appname = doc["appname"]
    admins = doc["admins"]

    @classmethod
    def is_admin(cls, sender):
        """Return True if sender is an admin, otherwise return False."""
        name, mail = email.Utils.parseaddr(sender)
        return mail.lower() in (email.lower() for email in cls.admins)

    @classmethod
    def get_subscriptions(cls, body):
        """Return generator of subscription dictionaries from body."""
        for line in body.splitlines():
            if not line.strip():  # Skip any blank lines in body
                continue
            yield dict(zip(['name', 'mail', 'team', 'status', 'role'],
                       [x.strip() for x in line.split(',')]))

    @classmethod
    def update_subscription(cls, data):
        """Updates subscription model with supplied data or creates new one."""
        subscriber = model.Subscriber.get_or_insert(**data)
        subscriber.status = data.get('status', 'subscribe')
        subscriber.role = data.get('role')
        subscriber.put()

    @classmethod
    def get_subscription_report(cls, subscriptions):
        """Return text report from sequence of Subscription dictionaries."""
        return '\n'.join([u'{name} <{mail}> {team} {status} {role}'
               .format(**x)
               for x in subscriptions])

    @classmethod
    def get_subscription_msg(cls, to, report):
        """Returns EmailMessage for supplied recipient and report."""
        app_id = app_identity.get_application_id()
        reply_to = '%s <noreply@%s.appspotmail.com>' % (cls.appname, app_id)
        fields = dict(
            sender=reply_to,
            to=to,
            reply_to=reply_to,
            subject='[%s] Admin confirmation - Your changes were saved' % cls.appname,
            body=report)
        return mail.EmailMessage(**fields)

    @classmethod
    def process_message(cls, sender, body):
        """Process subscription lines in body and send report to sender."""
        if not cls.is_admin(sender):
            logging.info('Ignoring admin request from non-admin %s' % sender)
            return
        map(cls.update_subscription, cls.get_subscriptions(body))
        report = cls.get_subscription_report(
            [x.to_dict() for x in model.Subscriber.query().iter()])
        cls.get_subscription_msg(sender, report).send()

    def receive(self, message):
        """Receive mail, create/update subscriptions, mail confirmation."""
        body = [b.decode() for t, b in message.bodies('text/plain')][0]
        self.process_message(message.sender, body)

routes = [
    AdminHandler.mapping(),
]

handlers = webapp2.WSGIApplication(routes, debug=True)
