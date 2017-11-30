import json
import math
import dateutil.parser
from datetime import datetime
import time
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


""" --- Helpers to build responses which match the structure of the necessary dialog actions --- """


def get_slots(intent_request):
    return intent_request['currentIntent']['slots']


def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message, response_card):
    logger.debug('elicit_slot {}'.format(slot_to_elicit))
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'message': message,
            'responseCard': response_card
        }
    }

    
def confirm_intent(session_attributes, intent_name, slots, message, response_card):
    logger.debug('confirm intent')
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ConfirmIntent',
            'intentName': intent_name,
            'slots': slots,
            'message': message,
            'responseCard': response_card
        }
    }


def close(session_attributes, fulfillment_state, message, response_card):
    logger.debug('close message={}'.format(message))

    response = {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': fulfillment_state,
            'message': message,
            'responseCard': response_card
        }
    }

    return response


def delegate(session_attributes, slots):
    logger.debug('delegate')
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }


def build_response_card(title, subtitle, options):
    """
    Build a responseCard with a title, subtitle, and an optional set of options which should be displayed as buttons.
    """
    logger.debug('build_response_card={}'.format(title))
    buttons = None
    if options is not None:
        buttons = []
        for i in range(min(5, len(options))):
            buttons.append(options[i])

    return {
        'contentType': 'application/vnd.amazonaws.card.generic',
        'version': 1,
        'genericAttachments': [{
            'title': title,
            'subTitle': subtitle,
            'buttons': buttons
        }]
    }


def build_options(session_date, session_time, agenda_json, type_set):
    logger.debug('build_options')

    options = []

    for session_type in type_set:
        # Find the session based on input
        s = find_session(session_type, session_date, session_time, agenda_json)
        if s:
            options.append({'text':'{} at {}'.format(s['track'], s['start']), 
                            'value':session_type})
            logger.debug('session_name={}'.format(s['name']))

    return options 
    

""" --- Helper Functions --- """
def parse_int(n):
    try:
        return int(n)
    except ValueError:
        return float('nan')


def build_validation_result(is_valid, violated_slot, message_content):
    if message_content is None:
        return {
            "isValid": is_valid,
            "violatedSlot": violated_slot
        }

    return {
        'isValid': is_valid,
        'violatedSlot': violated_slot,
        'message': {'contentType': 'PlainText', 'content': message_content}
    }


def isvalid_date(date):
    try:
        dateutil.parser.parse(date)
        return True
    except ValueError:
        return False


def find_session(session_type, session_date, session_time, agenda_json):
    # Note the agenda json must be ranked in the start field
    sessions = json.loads(agenda_json)
    if session_type:
        for s in sessions:
            if (s['track'].lower() == session_type.lower()) and (s['date'] == session_date):
                if s['start'] > session_time:
                    return s


def validate_conference_booking(session_type, session_date, session_time, type_set):
    if session_type is not None and session_type.lower() not in type_set:
        logger.debug('validate_conference_booking {}'.format(type_set))
        return build_validation_result(False,
                                       'SessionType',
                                       'We cannot find a track named {}. The available tracks are Inspire Me, Tech Specific and Seminar'.format(session_type))

    if session_date is not None:
        logger.debug('validate_conference_booking {}'.format(session_date))
        if not isvalid_date(session_date):
            return build_validation_result(False, 'SessionDate', 'I did not understand that, what date would you like to check? e.g. 2017-11-08')
        elif dateutil.parser.parse(session_date).date() != datetime.strptime('2017-11-08', '%Y-%m-%d').date():
            return build_validation_result(False, 'SessionDate', 'Sorry, we only have one day agenda for this demo. Please input the conference day 2017-11-08.')

    if session_time is not None:
        logger.debug('validate_conference_booking {}'.format(session_time))
        if len(session_time) != 5:
            # Not a valid time; use a prompt defined on the build-time model.
            return build_validation_result(False, 'SessionTime', None)

        hour, minute = session_time.split(':')
        hour = parse_int(hour)
        minute = parse_int(minute)
        if math.isnan(hour) or math.isnan(minute):
            # Not a valid time; use a prompt defined on the build-time model.
            return build_validation_result(False, 'SessionTime', None)

        if hour < 8 or hour > 17:
            # Outside of business hours
            return build_validation_result(False, 'SessionTime', 'The conference hours are from 9am to 6pm. Can you specify a time during this range?')

    return build_validation_result(True, None, None)


""" --- Functions that control the bot's behavior --- """


def book_session(intent_request):
    """
    Performs dialog management and fulfillment for booking a conference session.
    Beyond fulfillment, the implementation of this intent demonstrates the use of the elicitSlot dialog action
    in slot validation and re-prompting.
    """
    logger.debug('book_session {}'.format(intent_request))
    
    # Those values should be read from an external file in real use cases
    session_types = ['inspire me', 'tech specific', 'seminar']
    agenda_json = '[{"name":"Opening Remarks", "track":"Inspire Me", "date":"2017-11-08", "start":"09:15", "end":"09:30"},{"name":"How Technology Lets You Be YOU", "track":"Inspire Me", "date":"2017-11-08", "start":"09:30", "end":"10:00"},{"name":"The Invisible Made Visible", "track":"Inspire Me", "date":"2017-11-08", "start":"10:00", "end":"10:30"},{"name":"Business and Cultural Transformation in a Digital World", "track":"Inspire Me", "date":"2017-11-08", "start":"10:30", "end":"11:00"},{"name":"How Agile Tribes support WiT", "track":"Inspire Me", "date":"2017-11-08", "start":"11:00", "end":"11:30"},{"name":"The Road Ahead", "track":"Inspire Me", "date":"2017-11-08", "start":"11:30", "end":"12:00"},{"name":"Quantifying the Effect of D&I Policy", "track":"Inspire Me", "date":"2017-11-08", "start":"12:00", "end":"12:30"},{"name":"How We Try to Make a Lion Bulletproof", "track":"Inspire Me", "date":"2017-11-08", "start":"12:30", "end":"13:00"},{"name":"Leading Teams in Tech", "track":"Inspire Me", "date":"2017-11-08", "start":"14:00", "end":"14:30"},{"name":"Using Situational Awareness to Make Decisions", "track":"Inspire Me", "date":"2017-11-08", "start":"14:30", "end":"15:00"}, {"name":"How to Take Charge of your Life-Work Balance and Succeed in Ever-Changing Technology World", "track":"Inspire Me", "date":"2017-11-08", "start":"15:00", "end":"15:30"},{"name":"The Road Less Traveled By: Engineering a Career in Cybersecurity", "track":"Inspire Me", "date":"2017-11-08", "start":"16:00", "end":"16:30"},{"name":"An Engineering Managers Toolkit", "track":"Inspire Me", "date":"2017-11-08", "start":"16:30", "end":"17:00"},{"name":"The Path for Women to Rule the Technology World", "track":"Inspire Me", "date":"2017-11-08", "start":"17:00", "end":"17:30"},{"name":"Big Data: Myths vs Realities", "track":"Tech Specific", "date":"2017-11-08", "start":"11:30", "end":"12:00"},{"name":"Browser Peer to Peer Connections for Fun and Profit", "track":"Tech Specific", "date":"2017-11-08", "start":"12:00", "end":"12:30"},{"name":"Building an AI that Respects your Privacy", "track":"Tech Specific", "date":"2017-11-08", "start":"12:30", "end":"13:00"},{"name":"Geek + E.I. = Success in AI", "track":"Tech Specific", "date":"2017-11-08", "start":"14:00", "end":"14:30"},{"name":"Machine Learning Around Us", "track":"Tech Specific", "date":"2017-11-08", "start":"14:30", "end":"15:00"},{"name":"Metabolic Modelling Software", "track":"Tech Specific", "date":"2017-11-08", "start":"15:00", "end":"15:30"},{"name":"Project Liftoff", "track":"Tech Specific", "date":"2017-11-08", "start":"16:00", "end":"16:30"},{"name":"New Kid on the Block(Chain)", "track":"Tech Specific", "date":"2017-11-08", "start":"16:30", "end":"17:00"},{"name":"Optimizing Scrolling Performance of UITableView&UICollectionView", "track":"Tech Specific", "date":"2017-11-08", "start":"17:00", "end":"17:30"},{"name":"Augmented Reality: Past, Present & Future", "track":"Seminar", "date":"2017-11-08", "start":"12:30", "end":"13:00"},{"name":"Afraid of being Found Out: Kicking Imposter Syndrome in its Stupid Face!", "track":"Seminar", "date":"2017-11-08", "start":"14:00", "end":"15:00"},{"name":"Developing for the Human Experience", "track":"Seminar", "date":"2017-11-08", "start":"15:00", "end":"15:30"},{"name":"How to Build a Team; Diversity & Gender Inclusivity", "track":"Seminar", "date":"2017-11-08", "start":"17:00", "end":"17:30"}]'

    session_type = get_slots(intent_request)["SessionType"]
    session_date = get_slots(intent_request)["SessionDate"]
    session_time = get_slots(intent_request)["SessionTime"]
    output_session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}
    source = intent_request['invocationSource']

    logger.debug('book_session for {}, {}, {}'.format(session_date, session_time, session_type))

    if source == 'DialogCodeHook':
        # Perform basic validation on the supplied input slots.
        # Use the elicitSlot dialog action to re-prompt for the first violation detected.
        slots = get_slots(intent_request)
        
        validation_result = validate_conference_booking(session_type, session_date, session_time, session_types)
        if not validation_result['isValid']:
            slots[validation_result['violatedSlot']] = None
            
            return elicit_slot(intent_request['sessionAttributes'],
                               intent_request['currentIntent']['name'],
                               slots,
                               validation_result['violatedSlot'],
                               validation_result['message'],
                               None)

        if session_date and session_time and not session_type:
            content = "Sessions found: \n"
            for t in session_types:
                session = find_session(t, session_date, session_time, agenda_json)
                if session:
                    content = content + '-{} track: {} from {} to {}\n'.format(session['track'], session['name'], session['start'], session['end'])
                else:
                    content = content + '-{} track: None\n'.format(t)
                    
            return elicit_slot(
                output_session_attributes,
                intent_request['currentIntent']['name'],
                intent_request['currentIntent']['slots'],
                'SessionType',
                {
                    'contentType': 'PlainText', 
                    'content': content + '\nWhat track would you like to attend?'
                },
                build_response_card(
                    'Specify Track', 'What track would you like to attend?',
                    build_options(session_date, session_time, agenda_json, session_types)
                )
            )

        if session_date and session_time and session_type and intent_request['currentIntent']['confirmationStatus'] == 'None':
            session = find_session(session_type, session_date, session_time, agenda_json)
            return confirm_intent(
                output_session_attributes,
                intent_request['currentIntent']['name'],
                slots,
                {
                    'contentType': 'PlainText',
                    'content': 'Session {} in the {} track at {} on {}'.format
                                   (session['name'], session['track'], session['start'], session['date'])
                },
                build_response_card(
                    'Confirm attendence',
                    'Do you want to book the session?',
                    [{'text': 'yes', 'value': 'yes'}, {'text': 'no', 'value': 'no'}]
                )
            )

        # Pass the session information back through output session attributes to 
        # be used in various prompts defined on the bot model.
        return delegate(output_session_attributes, get_slots(intent_request))

    # Booking the session, and rely on the goodbye message of the bot to define the message to the end user.
    # In a real bot, this would likely involve a call to a backend service.
    return close(
        intent_request['sessionAttributes'],
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': 'Thank you. We have booked the session for you.'
        },
        build_response_card(
            'Rate the session',
            'What do you think about this session?',
            [{'text': 'Great!', 'value': '1'}, {'text': 'Fine.', 'value': '0'}, {'text': 'Boring :(', 'value': '-1'}]
        )
    )


""" --- Intents --- """

def dispatch(intent_request):
    """
    Called when the user specifies an intent for this bot.
    """

    logger.debug('dispatch userId={}, intentName={}'.format(intent_request['userId'], intent_request['currentIntent']['name']))

    intent_name = intent_request['currentIntent']['name']

    # Dispatch to your bot's intent handlers
    if intent_name == 'CheckConferenceAgenda':
        return book_session(intent_request)

    raise Exception('Intent with name ' + intent_name + ' not supported')


""" --- Main handler --- """
def lambda_handler(event, context):
    """
    Route the incoming request based on intent.
    The JSON body of the request is provided in the event slot.
    """
    # By default, treat the user request as coming from the America/New_York time zone.
    os.environ['TZ'] = 'America/New_York'
    time.tzset()
    logger.debug('event.bot.name={}'.format(event['bot']['name']))

    return dispatch(event)
