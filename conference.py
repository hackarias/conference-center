#!/usr/bin/env python
from datetime import datetime
import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb
from models import ConflictException
from models import Session
from models import SessionForm
from models import SessionForms
from models import TypeOfSession
from models import Speaker
from models import SpeakerForm
from models import SpeakerForms
from models import Profile
from models import ProfileMiniForm
from models import ProfileForm
from models import StringMessage
from models import BooleanMessage
from models import Conference
from models import ConferenceForm
from models import ConferenceForms
from models import ConferenceQueryForms
from models import TeeShirtSize
from settings import WEB_CLIENT_ID
from settings import ANDROID_CLIENT_ID
from settings import IOS_CLIENT_ID
from settings import ANDROID_AUDIENCE
from utils import getUserId

__author__ = 'wesc+api@google.com (Wesley Chun)'
"""
conference.py -- Udacity conference server-side Python App Engine API;
    uses Google Cloud Endpoints

$Id: conference.py,v 1.25 2014/05/24 23:42:19 wesc Exp wesc $

created by wesc on 2014 apr 21

"""

EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID
MEMCACHE_FEATURED_SPEAKER_KEY = "FEATURED SPEAKER"
MEMCACHE_ANNOUNCEMENTS_KEY = "RECENT_ANNOUNCEMENTS"
FEATURED_SPEAKER_ANNOUNCEMENT = "Conference %s: \n" \
                                "Speaker: %s \n" \
                                "Sessions: %s"
ANNOUNCEMENT_TPL = ('Last chance to attend! The following conferences '
                    'are nearly sold out: %s')
# - - - - Globals - - - - - - - - - - - - - - - - - - - - - - - - -
SESS_DEFAULTS = {"duration": 0, "typeOfSession": TypeOfSession.Not_Specified}

CONF_DEFAULTS = {
    "city": "Default City",
    "maxAttendees": 0,
    "seatsAvailable": 0,
    "topics": ["Default", "Topic"],
}

OPERATORS = {
    'EQ': '=',
    'GT': '>',
    'GTEQ': '>=',
    'LT': '<',
    'LTEQ': '<=',
    'NE': '!='
}

FIELDS = {
    'CITY': 'city',
    'TOPIC': 'topics',
    'MONTH': 'month',
    'MAX_ATTENDEES': 'maxAttendees',
}

SPEAKER_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1))

SPEAKER_BY_CONFERENCE_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1))

WISHLIST_POST_REQUEST = endpoints.ResourceContainer(
    websafeSessionKey=messages.StringField(1))

SESS_BY_SPEAKER_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    speakerKey=messages.StringField(1, required=True))

SESS_BY_DATE_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1, required=True),
    date=messages.StringField(2, required=True))

SESS_BY_TYPE_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1, required=True),
    typeOfSession=messages.StringField(2, required=True))

SESS_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1))

SESS_POST_REQUEST = endpoints.ResourceContainer(
    SessionForm,
    websafeConferenceKey=messages.StringField(1))

CONF_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1))

CONF_POST_REQUEST = endpoints.ResourceContainer(
    ConferenceForm,
    websafeConferenceKey=messages.StringField(1))


@endpoints.api(name='conference',
               version='v1',
               audiences=[ANDROID_AUDIENCE],
               allowed_client_ids=[WEB_CLIENT_ID, API_EXPLORER_CLIENT_ID,
                                   ANDROID_CLIENT_ID, IOS_CLIENT_ID],
               scopes=[EMAIL_SCOPE])
class ConferenceApi(remote.Service):
    """Conference API v0.1"""

    # - - - - Wishlist section - - - - - - - - - - - - - - - - - -
    def _add_session_to_wishlist(self, request, add=True):
        """ adds the session to the user's list of session they are interested
         in attending
        """
        # Make sure that the user is authenticated
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException("Authorization required.")
        # Get the users profile
        prof = self._get_profile_from_user()
        # check if conf exists given websafeConfKey
        # get session; check that it exists

        try:
            s_key = ndb.Key(urlsafe=request.websafeConferenceKey)
        except Exception:
            raise endpoints.BadRequestException(
                "the websafeSessionKey given is not valid.")

        # Check if the session exists
        session = s_key.get()
        if not session:
            raise endpoints.NotFoundException(
                'No session found with key: {}').format(session)

        conf = session.key.parent().get()
        c_key = conf.key.urlsafe()
        # Add to wishlist
        if add:
            # Check if user already has this session in wishlist
            if c_key in prof.sessionWishList:
                raise ConflictException(
                    "You have already have this session in your wishlist")
            # Go ahead and add it to the wishlist
            # Add to wishlist
            prof.sessionWishList.append(c_key)
            return_value = True
        # Remove session from wishlist
        else:
            # check if user already registered
            if c_key in prof.sessionWishList:
                # Remove session
                prof.sessionWishList.remove(c_key)
                return_value = True
            else:
                return_value = False

        # Write changes back to the datastore & return
        prof.put()
        return BooleanMessage(data=return_value)

    @endpoints.method(WISHLIST_POST_REQUEST,
                      BooleanMessage,
                      path="addSessionToWishList/{websafeSessionKey}",
                      http_method="POST",
                      name="addSessionToWishList")
    def add_session_to_wishlist(self, request):
        """
        adds the session to the user's list of sessions they are interested in
        attending
        """
        return self._add_session_to_wishlist(request)

    @endpoints.method(SESS_POST_REQUEST,
                      BooleanMessage,
                      path="removeSessionFromWishList/{websafeConferenceKey}",
                      http_method="DELETE",
                      name="removeSessionFromWishList")
    def remove_session_from_wishlist(self, request):
        """
        Removes the session from the user's list of session they are interest
        in attending
        """
        return self._add_session_to_wishlist(request)

    @endpoints.method(message_types.VoidMessage,
                      SessionForms,
                      path='wishlist',
                      http_method='GET',
                      name='getSessionsInWishList')
    def get_sessions_in_wishlist(self, request):
        """
        Query for all the sessions in a conference that the user is interested
        in
        """
        # Get the users profile
        user = self._get_profile_from_user()
        # Get keys in wishlist
        s_keys = [ndb.Key(urlsafe=wsck) for wsck in user.sessionWishList]
        sessions = ndb.get_multi(s_keys)
        return SessionForms(
            items=[self._copy_session_to_form(s) for s in sessions])

    # - - - - Speaker section - - - - - - - - - - - - - - - - - -
    @endpoints.method(SPEAKER_GET_REQUEST,
                      SpeakerForms,
                      path="conferenceSpeaker/{websafeConferenceKey}",
                      http_method="GET",
                      name="getSpeakers")
    def get_speakers(self, request):
        """ Returns all the speakers for a given conference """
        # Make sure that the user is authenticated
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException("Authorization required.")
        # Try to get the conference key
        try:
            c_key = ndb.Key(urlsafe=request.websafeConferenceKey)
        except Exception:
            raise endpoints.BadRequestException(
                "websafeConferenceKey: %s is invalid"
                % request.websafeConferenceKey)
        # Filter on the conferences's sessions
        sessions = Session.query(ancestor=c_key).fetch()
        # Get rid of duplicates
        unique_speakers = set([session.speakerKey for session in sessions])
        speakers = ndb.get_multi(unique_speakers)
        return SpeakerForms(items=[SpeakerForm(name=getattr(name, 'name'))
                                   for name in speakers])

    @endpoints.method(CONF_GET_REQUEST,
                      SpeakerForms,
                      path="getSpeakersByConference/{websafeConferenceKey}",
                      http_method="GET",
                      name="getSpeakersByConference")
    def get_speakers_by_conference(self, request):
        """ Returns all speakers from given conference """
        # Make sure that the user is authenticated
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException("Authorization required.")

        # Get speakerKey
        speaker_key = Speaker.query(
            ancestor=ndb.Key(urlsafe=request.speakerKey))
        return SpeakerForms(
            items=[self._copy_speaker_to_form(s) for s in speaker_key])

    @endpoints.method(SpeakerForm,
                      SpeakerForm,
                      path="createSpeaker",
                      http_method="POST",
                      name="createSpeakerObject")
    def create_speaker(self, request):
        """  Create new speaker """
        return self._create_speaker_object(request)

    def _create_speaker_object(self, request):
        """ Creates a Speaker object """

        # Make sure that the user is authenticated
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException("Authorization required.")

        if not request.name:
            raise endpoints.BadRequestException("Speaker 'name' required.")

        # Copy SpeakerForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name)
                for field in request.all_fields()}

        # Generate key for Speaker using Session and the Speaker ID
        s_id = Session.allocate_ids(size=1)[0]
        s_key = ndb.Key(Speaker, s_id)
        data['key'] = s_key

        # Create Speaker
        Speaker(**data).put()
        return request

    def _copy_speaker_to_form(self, copy_speaker):
        """ Copy relevant fields from Speaker to SpeakerForm """
        sf = SpeakerForm()
        for field in sf.all_fields():
            if hasattr(copy_speaker, field.name):
                setattr(sf, field.name, getattr(copy_speaker, field.name))
            elif field.name == "websafeKey":
                setattr(sf, field.name, copy_speaker.key.urlsafe())
        sf.check_initialized()
        return sf

    # - - - - Conference section - - - - - - - - - - - - - - - - - -
    def _copy_conference_to_form(self, conf, display_name):
        """Copy relevant fields from Conference to ConferenceForm."""
        cf = ConferenceForm()
        for field in cf.all_fields():
            if hasattr(conf, field.name):
                # convert Date to date string; just copy others
                if field.name.endswith('Date'):
                    setattr(cf, field.name, str(getattr(conf, field.name)))
                else:
                    setattr(cf, field.name, getattr(conf, field.name))
            elif field.name == "websafeKey":
                setattr(cf, field.name, conf.key.urlsafe())
        if display_name:
            setattr(cf, 'organizerDisplayName', display_name)
        cf.check_initialized()
        return cf

    def _create_conference_object(self, request):
        """

        Create or update Conference object, returning ConferenceForm/request.
        """
        # preload necessary data items
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        if not request.name:
            raise endpoints.BadRequestException(
                "Conference 'name' field required")

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name)
                for field in request.all_fields()}
        del data['websafeKey']
        del data['organizerDisplayName']

        # Add default values for those missing
        # (both data model & outbound Message)
        for df in CONF_DEFAULTS:
            if data[df] in (None, []):
                data[df] = CONF_DEFAULTS[df]
                setattr(request, df, CONF_DEFAULTS[df])

        # convert dates from strings to Date objects.
        # set month based on start_date
        if data['startDate']:
            data['startDate'] = datetime.strptime(data['startDate'][:10],
                                                  "%Y-%m-%d").date()
            data['month'] = data['startDate'].month
        else:
            data['month'] = 0
        if data['endDate']:
            data['endDate'] = datetime.strptime(data['endDate'][:10],
                                                "%Y-%m-%d").date()

        # set seatsAvailable to be same as maxAttendees on creation
        if data["maxAttendees"] > 0:
            data["seatsAvailable"] = data["maxAttendees"]
        # generate Profile Key based on user ID and Conference
        # ID based on Profile key get Conference key from ID
        p_key = ndb.Key(Profile, user_id)
        c_id = Conference.allocate_ids(size=1, parent=p_key)[0]
        c_key = ndb.Key(Conference, c_id, parent=p_key)
        data['key'] = c_key
        data['organizerUserId'] = request.organizerUserId = user_id

        # create Conference, send email to organizer confirming
        # creation of Conference & return (modified) ConferenceForm
        Conference(**data).put()
        taskqueue.add(params={'email': user.email(),
                              'conferenceInfo': repr(request)},
                      url='/tasks/send_confirmation_email')
        return request

    @ndb.transactional()
    def _update_conference_object(self, request):
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # update existing conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        # check that conference exists
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' %
                request.websafeConferenceKey)

        # check that user is owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner can update the conference.')

        # Not getting all the fields, so don't create a new object; just
        # copy relevant fields from ConferenceForm to Conference object
        for field in request.all_fields():
            data = getattr(request, field.name)
            # only copy fields where we get data
            if data not in (None, []):
                # special handling for dates (convert string to Date)
                if field.name in ('startDate', 'endDate'):
                    data = datetime.strptime(data, "%Y-%m-%d").date()
                    if field.name == 'startDate':
                        conf.month = data.month
                # write to Conference object
                setattr(conf, field.name, data)
        conf.put()
        prof = ndb.Key(Profile, user_id).get()
        return self._copy_conference_to_form(conf,
                                             getattr(prof, 'displayName'))

    @endpoints.method(ConferenceForm,
                      ConferenceForm,
                      path='conference',
                      http_method='POST',
                      name='createConference')
    def create_conference(self, request):
        """Create new conference."""
        return self._create_conference_object(request)

    @endpoints.method(CONF_POST_REQUEST,
                      ConferenceForm,
                      path='conference/{websafeConferenceKey}',
                      http_method='PUT',
                      name='updateConference')
    def update_conference(self, request):
        """Update conference w/provided fields & return w/updated info."""
        return self._update_conference_object(request)

    @endpoints.method(CONF_GET_REQUEST,
                      ConferenceForm,
                      path='conference/{websafeConferenceKey}',
                      http_method='GET',
                      name='getConference')
    def get_conference(self, request):
        """Return requested conference by websafeConferenceKey."""
        # get Conference object from request; bail if not found
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' %
                request.websafeConferenceKey)
        prof = conf.key.parent().get()
        # return ConferenceForm
        return self._copy_conference_to_form(conf,
                                             getattr(prof, 'displayName'))

    @endpoints.method(message_types.VoidMessage,
                      ConferenceForms,
                      path='getConferencesCreated/{websafeConferenceKey}',
                      http_method='POST',
                      name='getConferenceCreated')
    def get_conferences_created(self, request):
        """Return conferences created by user."""
        # Make sure user is authenticated
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # Create ancestor query for all key matches for this user
        conferences = Conference.query(ancestor=ndb.Key(Profile, user_id))
        prof = ndb.Key(Profile, user_id).get()
        # return set of ConferenceForm objects per Conference
        return ConferenceForms(items=[
            self._copy_conference_to_form(conf, getattr(
                prof, 'displayName')) for conf in conferences
            ])

    @endpoints.method(ConferenceQueryForms,
                      ConferenceForms,
                      path='queryConferences',
                      http_method='POST',
                      name='queryConferences')
    def query_conferences(self, request):
        """Query for conferences."""
        conferences = self._get_query(request)

        # need to fetch organiser displayName from profiles
        # get all keys and use get_multi for speed
        organisers = [(ndb.Key(Profile, conf.organizerUserId))
                      for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return individual ConferenceForm object per Conference
        return ConferenceForms(items=[
            self._copy_conference_to_form(conf, names[
                conf.organizerUserId]) for conf in conferences])

    # - - - - Filters section - - - - - - - - - - - - - - - - - -
    def _format_filters(self, filters):
        """Parse, check validity and format user supplied filters."""
        formatted_filters = []
        inequality_field = None

        for f in filters:
            filtr = {field.name: getattr(f, field.name)
                     for field in f.all_fields()}

            try:
                filtr["field"] = FIELDS[filtr["field"]]
                filtr["operator"] = OPERATORS[filtr["operator"]]
            except KeyError:
                raise endpoints.BadRequestException(
                    "Filter contains invalid field or operator.")

            # Every operation except "=" is an inequality
            if filtr["operator"] != "=":
                """
                Check if inequality operation has been used in previous
                filters.
                Disallow the filter if inequality was performed on a different
                field before.
                Track the field on which the inequality operation is performed.
                """
                if inequality_field and inequality_field != filtr["field"]:
                    raise endpoints.BadRequestException(
                        "Inequality filter is allowed on only one field.")
                else:
                    inequality_field = filtr["field"]

            formatted_filters.append(filtr)
        return inequality_field, formatted_filters

    # - - - - Query section - - - - - - - - - - - - - - - - - -
    def _get_query(self, request):
        """Return formatted query from the submitted filters."""
        q = Conference.query()
        inequality_filter, filters = self._format_filters(request.filters)
        # If exists, sort on inequality FILTER first
        if not inequality_filter:
            q = q.order(Conference.name)
        else:
            q = q.order(ndb.GenericProperty(inequality_filter))
            q = q.order(Conference.name)
        for FILTER in filters:
            if FILTER["field"] in ["month", "maxAttendees"]:
                FILTER["value"] = int(FILTER["value"])
            formatted_query = ndb.query.FilterNode(
                FILTER["field"], FILTER["operator"], FILTER["value"])
            q = q.filter(formatted_query)
        return q

    # - - - Session objects - - - - - - - - - - - - - - - - -

    @endpoints.method(SESS_BY_DATE_GET_REQUEST,
                      SessionForms,
                      path="getSessionsByDate/{websafeConferenceKey}/{date}",
                      http_method="GET",
                      name="getSessionsByDate")
    def get_sessions_by_date(self, request):
        """ Return all sessions by date. """
        # Make sure that the user is authenticated
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException("Authorization required.")

        # Get conference key and filter on sessions
        sessions = Session.query(
            ancestor=ndb.Key(urlsafe=request.websafeConferenceKey))
        date = datetime.strptime(request.date[:10], "%Y-%m-%d").date()
        # Filter by date
        sessions = sessions.filter(Session.date == date)
        # Return SessionForm as Session
        return SessionForms(
            items=[self._copy_session_to_form(s) for s in sessions])

    # - - - - Speaker section - - - - - - - - - - - - - - - - - -
    @endpoints.method(SESS_BY_SPEAKER_GET_REQUEST,
                      SessionForms,
                      path="getSessionsBySpeaker/"
                           "{speakerKey}",
                      http_method="GET",
                      name="getSessionsBySpeaker")
    def get_sessions_by_speaker(self, request):
        """
        Given a speakerKey, return all sessions given by this particular
        speakerKey, across all conferences.
        """
        # Make sure user is authenticated
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException("Authorization required.")
        # Filter on speakerKey
        sessions = Session.query(Session.speakerKey == request.speakerKey)
        # Return a SessionForm as Session
        return SessionForms(
            items=[self._copy_session_to_form(s) for s in sessions])

    @endpoints.method(SESS_BY_TYPE_GET_REQUEST,
                      SessionForms,
                      path="getSessionsByType/"
                           "{websafeConferenceKey}/{typeOfSession}",
                      http_method="GET",
                      name="getSessionsByType")
    def get_sessions_by_type(self, request):
        """
        Given a conference, return all sessions of a specified type
        (eg lecture, keynote, workshop)
        """
        # Make sure that the user is authenticated
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException("Authorization required.")

        # Query for session keys
        s_key = Session.query(
            ancestor=ndb.Key(urlsafe=request.websafeConferenceKey))
        # Filter on type of session
        sessions = s_key.filter(Session.typeOfSession == request.typeOfSession)
        return SessionForms(
            items=[self._copy_session_to_form(s) for s in sessions])

    @endpoints.method(CONF_GET_REQUEST,
                      SessionForms,
                      path="sessions/{websafeConferenceKey}",
                      http_method="GET",
                      name="getSessions")
    def get_sessions(self, request):
        """ Given a conference, return all sessions """
        user = endpoints.get_current_user()

        # Auth the user
        if not user:
            raise endpoints.UnauthorizedException("Authorization required")

        # Try to get the Conference key
        try:
            c_key = ndb.Key(urlsafe=request.websafeConferenceKey)
        except Exception:
            raise endpoints.BadRequestException(
                "websafeConferenceKey is not valid.")
        conf = c_key.get()
        # Check if the conference exists
        if not conf:
            raise endpoints.NotFoundException(
                "Could not find corresponding key to conference."
                " Key: {}".format(request.websafeConferenceKey))
        # Get the conferences sessions
        sessions = Session.query(ancestor=c_key)
        # Return a SessionForm for a Session
        return SessionForms(
            items=[self._copy_session_to_form(sess) for sess in sessions])

    def _create_session_object(self, request):
        global speaker
        user = endpoints.get_current_user()
        # Auth the user
        if not user:
            raise endpoints.UnauthorizedException("Authorization required")

        user_id = getUserId(user)

        if not request.name:
            raise endpoints.BadRequestException(
                "Session 'name' field required")

        # We are going to need information from the Conference the session
        # belongs to.
        try:
            c_key = ndb.Key(urlsafe=request.parentConference)
        except Exception:
            raise endpoints.BadRequestException("Parent conference is invalid")

        conference = c_key.get()
        # Check that the current user is the same who created the conference
        if user_id != conference.organizerUserId:
            raise endpoints.ForbiddenException(
                "You have to be the creator of the conference to create a"
                " session")
        # Check if the speakerKey is valid
        if request.speakerKey:
            try:
                speaker = ndb.Key(urlsafe=request.speakerKey).get()
            except Exception:
                raise endpoints.BadRequestException(
                    "speakerKey {} is not valid.".format(speaker))

        # Copy SessionForm/ProtoRPC Message into dict.
        data = {field.name: getattr(request, field.name)
                for field in request.all_fields()}
        # Add default values for those missing
        # (both data model & outbound Message)
        for df in SESS_DEFAULTS:
            if data[df] in (None, []):
                data[df] = SESS_DEFAULTS[df]
                setattr(request, df, SESS_DEFAULTS[df])
        # Convert dates from strings to Date objects
        if data['date']:
            data['date'] = (datetime.strptime(data['date'][:10],
                                              "%Y-%m-%d").date())
        # Convert startTime to Time object from string
        if data['startTime']:
            data['startTime'] = datetime.strptime(data['startTime'][:5],
                                                  "%H:%M").time()
        # Convert typOfSession to string
        if data['typeOfSession']:
            data['typeOfSession'] = str(data['typeOfSession'])

        # Generate profile key based on user ID and Session
        # ID based on Profile key get Conference key from ID
        p_key = ndb.Key(Profile, user_id)
        s_id = Session.allocate_ids(size=1, parent=p_key)[0]
        s_key = ndb.Key(Session, s_id, parent=p_key)
        data['key'] = s_key

        Session(**data).put()
        return request

    def _copy_session_to_form(self, sess):
        """Copy relevant fields from Session to SessionForm."""
        sf = SessionForm()
        for field in sf.all_fields():
            if hasattr(sess, field.name):
                # convert date to date string; just copy others
                if field.name == 'date' or field.name == "startTime":
                    setattr(sf, field.name, str(getattr(sess, field.name)))
                # Convert typeOfSession to enum
                elif field.name == "typeOfSession":
                    setattr(sf, field.name,
                            getattr(TypeOfSession, getattr(sess, field.name)))
                else:
                    setattr(sf, field.name, getattr(sess, field.name))
            elif field.name == "websafeConferenceKey":
                setattr(sf, field.name, sess.key.urlsafe())
        sf.check_initialized()
        return sf

    @endpoints.method(SessionForm,
                      SessionForm,
                      path="session",
                      http_method="POST",
                      name="createSession")
    def create_session(self, request):
        """ Create new session """
        return self._create_session_object(request)

    # - - - Profile objects - - - - - - - - - - - - - - - - - - -
    @endpoints.method(message_types.VoidMessage,
                      ProfileForm,
                      path='profile',
                      http_method='GET',
                      name='getProfile')
    def get_profile(self, request):
        """Return user profile."""
        return self._do_profile()

    @endpoints.method(ProfileMiniForm,
                      ProfileForm,
                      path='profile',
                      http_method='POST',
                      name='saveProfile')
    def save_profile(self, request):
        """Update & return user profile."""
        return self._do_profile(request)

    def _copy_profile_to_form(self, prof):
        """Copy relevant fields from Profile to ProfileForm."""
        pf = ProfileForm()
        for field in pf.all_fields():
            if hasattr(prof, field.name):
                # convert t-shirt string to Enum; just copy others
                if field.name == 'teeShirtSize':
                    setattr(pf, field.name,
                            getattr(TeeShirtSize, getattr(prof, field.name)))
                else:
                    setattr(pf, field.name, getattr(prof, field.name))
        pf.check_initialized()
        return pf

    def _get_profile_from_user(self):
        """
        Return user Profile from datastore, creating new one if non-existent.
        """
        # Make sure user is authenticated
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # get Profile from datastore
        user_id = getUserId(user)
        p_key = ndb.Key(Profile, user_id)
        profile = p_key.get()
        # create new Profile if not there
        if not profile:
            profile = Profile(key=p_key,
                              displayName=user.nickname(),
                              mainEmail=user.email(),
                              teeShirtSize=str(TeeShirtSize.NOT_SPECIFIED), )
            profile.put()

        return profile  # return Profile

    def _do_profile(self, save_request=None):
        """Get user Profile and return to user, possibly updating it first."""
        # get user Profile
        prof = self._get_profile_from_user()

        # if save_profile(), process user-modifiable fields
        if save_request:
            for field in ('displayName', 'teeShirtSize'):
                if hasattr(save_request, field):
                    val = getattr(save_request, field)
                    if val:
                        setattr(prof, field, str(val))
                        if field == 'teeShirtSize':
                            setattr(prof, field, str(val).upper())
                        else:
                            setattr(prof, field, val)
                    prof.put()

        # return ProfileForm
        return self._copy_profile_to_form(prof)

    # - - - Announcements - - - - - - - - - - - - - - - - - - - -
    @staticmethod
    def _cache_announcement():
        """Create Announcement & assign to memcache; used by
        memcache cron job & putAnnouncement().
        """
        conferences = Conference.query(
            ndb.AND(Conference.seatsAvailable <= 5, Conference.seatsAvailable >
                    0)).fetch(projection=[Conference.name])

        if conferences:
            # If there are almost sold out conferences,
            # format announcement and set it in memcache
            announcement = ANNOUNCEMENT_TPL % (
                ', '.join(conf.name for conf in conferences))
            memcache.set(MEMCACHE_ANNOUNCEMENTS_KEY, announcement)
        else:
            # If there are no sold out conferences,
            # delete the memcache announcements entry
            announcement = ""
            memcache.delete(MEMCACHE_ANNOUNCEMENTS_KEY)
        return announcement

    @endpoints.method(message_types.VoidMessage,
                      StringMessage,
                      path='conference/announcement/get',
                      http_method='GET',
                      name='getAnnouncement')
    def get_announcement(self):
        """Return Announcement from memcache."""
        return StringMessage(
            data=memcache.get(MEMCACHE_ANNOUNCEMENTS_KEY) or "")

    # - - - Registration - - - - - - - - - - - - - - - - - - - -
    @ndb.transactional(xg=True)
    def _conference_registration(self, request, reg=True):
        """Register or unregister user for selected conference."""
        prof = self._get_profile_from_user()  # get user Profile

        # check if conf exists given websafeConfKey
        # get conference; check that it exists
        wsck = request.websafeConferenceKey
        conf = ndb.Key(urlsafe=wsck).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % wsck)

        # register
        if reg:
            # check if user already registered otherwise add
            if wsck in prof.conferenceKeysToAttend:
                raise ConflictException(
                    "You have already registered for this conference")

            # check if seats avail
            if conf.seatsAvailable <= 0:
                raise ConflictException("There are no seats available.")

            # register user, take away one seat
            prof.conferenceKeysToAttend.append(wsck)
            conf.seatsAvailable -= 1
            return_value = True

        # unregister
        else:
            # check if user already registered
            if wsck in prof.conferenceKeysToAttend:

                # unregister user, add back one seat
                prof.conferenceKeysToAttend.remove(wsck)
                conf.seatsAvailable += 1
                return_value = True
            else:
                return_value = False

        # write things back to the datastore & return
        prof.put()
        conf.put()
        return BooleanMessage(data=return_value)

    @endpoints.method(message_types.VoidMessage,
                      ConferenceForms,
                      path='conferences/attending',
                      http_method='GET',
                      name='getConferencesToAttend')
    def get_conferences_to_attend(self, request):
        """Get list of conferences that user has registered for."""
        prof = self._get_profile_from_user()  # get user Profile
        conf_keys = [ndb.Key(urlsafe=wsck)
                     for wsck in prof.conferenceKeysToAttend]
        conferences = ndb.get_multi(conf_keys)

        # get organizers
        organizers = [ndb.Key(Profile, conf.organizerUserId)
                      for conf in conferences]
        profiles = ndb.get_multi(organizers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return set of ConferenceForm objects per Conference
        return ConferenceForms(items=[
            self._copy_conference_to_form(conf, names[
                conf.organizerUserId]) for conf in conferences])

    @endpoints.method(CONF_GET_REQUEST,
                      BooleanMessage,
                      path='conference/{websafeConferenceKey}',
                      http_method='POST',
                      name='registerForConference')
    def register_for_conference(self, request):
        """Register user for selected conference."""
        return self._conference_registration(request)

    @endpoints.method(CONF_GET_REQUEST,
                      BooleanMessage,
                      path='conference/{websafeConferenceKey}',
                      http_method='DELETE',
                      name='unregisterFromConference')
    def unregister_from_conference(self, request):
        """Unregister user for selected conference."""
        return self._conference_registration(request, reg=False)

    @endpoints.method(message_types.VoidMessage,
                      ConferenceForms,
                      path='filterPlayground',
                      http_method='GET',
                      name='filterPlayground')
    def filter_playground(self):
        """Filter Playground"""
        q = Conference.query()
        # field = "city"
        # operator = "="
        # value = "London"
        # f = ndb.query.FilterNode(field, operator, value)
        # q = q.filter(f)
        q = q.filter(Conference.city == "London")
        q = q.filter(Conference.topics == "Medical Innovations")
        q = q.filter(Conference.month == 6)

        return ConferenceForms(
            items=[self._copy_conference_to_form(conf, "") for conf in q])

    # - - - - Featured Speakers objects - - - - - - - - - - - - - - - - - -
    @staticmethod
    def _cache_featured_speaker(speaker_websafekey, conference_websafekey):
        """ Create an announcement for the featured speaker and assign it to
         memcache """
        # Get the speaker and conference keys
        conference_key = ndb.Key(urlsafe=conference_websafekey)
        speaker_key = ndb.Key(urlsafe=speaker_websafekey)
        sessions = Session.query(ancestor=conference_key).filter(
            Session.speakerKey == speaker_key)

        # Getting the required data and adding it to the announcement
        if sessions.count() > 1:
            conference = conference_key.get()
            speaker = speaker_key.get()
            sessions_names = ', '.join([x.name for x in sessions])
            if speaker:
                announcement = FEATURED_SPEAKER_ANNOUNCEMENT % (
                    conference.name,
                    speaker.name,
                    sessions_names)
                memcache.set(MEMCACHE_FEATURED_SPEAKER_KEY, announcement)
            else:
                announcement = ""
                memcache.delete(MEMCACHE_FEATURED_SPEAKER_KEY)

    @endpoints.method(message_types.VoidMessage, StringMessage,
                      path='features_speaker_announcement/get',
                      http_method='GET',
                      name='getFeaturedSpeaker')
    def get_featured_speaker(self, request):
        """Return Announcement from memcache."""
        return StringMessage(
            data=memcache.get(MEMCACHE_FEATURED_SPEAKER_KEY) or "")


api = endpoints.api_server([ConferenceApi])  # register API
