from django.shortcuts import render
from django.core.cache import cache
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.core.exceptions import ValidationError
from django.utils.decorators import method_decorator
from django.contrib.auth.models import User
from .models import User, UserProfile, UserDetails, UserDescription, ReceivedMessage, Message
from .serializers import UserProfileSerializer



@api_view(['POST'])
def message_receive_view(request):
    phone_number = request.data.get('phone_number')
    message = request.data.get('message')

    response_data = {}

    if not phone_number:
        return Response("Phone number is required.", status=400)

    user, created = User.objects.get_or_create(phone_number=phone_number)

    response_data = process_message(user, message)

    return Response(response_data)

def process_message(user, message):
    response_data = {}

    if message.lower() == 'penzi' and not user.is_registered:
        response_data['status'] = handle_penzi_unregistered(user)
    elif message.lower() == 'penzi' and user.is_registered:
        response_data['status'] = handle_penzi_registered(user)
    elif message.lower().startswith('start#') and not user.is_registered:
        response_data['status'] = handle_start_message(user, message)
    elif message.lower().startswith('details#') and user.is_registered:
        response_data['status'] = handle_details_message(user, message)
    elif message.lower().startswith('myself ') and user.is_registered:
        response_data['status'] = handle_myself_message(user, message)
    elif message.lower().startswith('match#') and user.is_registered:
        response_data['status'] = handle_match_message(user, message)
    elif message.lower() == 'next' and user.is_registered:
        response_data['status'] = handle_next_message(user)
    elif message.isdigit() and len(message) in (9, 10):
        response_data['status'] = handle_digit_message(user, message)
    elif message.lower().startswith('describe') and len(message.split()) == 2 and user.is_registered:
        response_data['status'] = handle_describe_message(user, message)
    elif message.lower() == 'yes' and user.is_registered:
        response_data['status'] = handle_yes_message(user, message)

    return response_data

def handle_penzi_unregistered(user):
    return 'Welcome to our dating service with 6000 potential dating partners! ' \
           'To register SMS start#name#age#gender#county#town to 22141. E.g., ' \
           'start#John Doe#26#Male#Nakuru#Naivasha'

def handle_penzi_registered(user):
    return 'You are registered for dating. To search for a MPENZI, SMS match#age#town ' \
           'to 22141 and meet the person of your dreams. E.g., match#23-25#Nairobi'


def handle_start_message(user, message):
    response_data = {}
    if message.lower().startswith('start#') and not user.is_registered:
        try:
            _, name, age, gender, county, town = message.split('#')
            age = int(age)
            if not (18 <= age <= 85):
                raise ValidationError("Age should be between 18 and 85.")

            if gender.lower().strip() not in ['male', 'female']:
                raise ValidationError("Gender should be 'male' or 'female'.")
        except ValueError:
            return {"status": "Invalid format. Please provide information in the format 'start#name#age#gender#county#town'"}, 400
        except ValidationError as e:
            return {"status": str(e)}, 400

        profile = UserProfile.objects.create(
            user=user,
            name=name,
            age=age,
            gender=gender,
            county=county,
            town=town
        )

        user.is_registered = True
        user.save()

        profile_serializer = UserProfileSerializer(profile)
        username = profile_serializer.data.get('name', '')

        response_data['status'] = f"Your profile has been created successfully, {username}. " \
                                   "SMS details#levelOfEducation#profession#maritalStatus#religion#ethnicity " \
                                   "to 22141. E.g. details#diploma#driver#single#christian#mijikenda"
    elif message.lower().startswith('start#') and user.is_registered:
        response_data['status'] = 'You are already registered.'

    return response_data

def handle_details_message(user, message):
    response_data = {}
    if message.lower().startswith('details#') and user.is_registered:
        try:
            _, level_of_education, profession, marital_status, religion, ethnicity = message.split('#')
        except ValueError:
            return {"status": "Invalid format. Please provide information in the format 'details#level_of_education#profession#marital_status#religion#ethnicity'"}, 400

        last_details_time = cache.get(f'user_{user.id}_last_details')
        if last_details_time:
            time_difference = timezone.now() - last_details_time
            if time_difference.total_seconds() > 60:  # Check if one minute has passed since 'details' message
                # Send a timeout response if one minute has elapsed since 'details' message
                response_data['status'] = f"You were registered for dating with your initial details. " \
                                          "To search for a MPENZI, SMS match#age#town " \
                                          "to 22141 and meet the person of your dreams. " \
                                          "E.g., match#23-25#Nairobi"
                # Clear the 'last_details' cache as timeout occurred
                cache.delete(f'user_{user.id}_last_details')
                return response_data

        user_details = UserDetails.objects.create(
            user=user,
            level_of_education=level_of_education,
            profession=profession,
            marital_status=marital_status,
            religion=religion,
            ethnicity=ethnicity
        )

        cache.set(f'user_{user.id}_last_details', timezone.now())

        response_data['status'] = f"This is the last stage of registration. " \
                                   "SMS a brief description of yourself to 22141 starting with the word " \
                                   "MYSELF." \
                                   "E.g., MYSELF chocolate, lovely, sexy etc."
    elif message.lower().startswith('details#') and not user.is_registered:
        response_data['status'] = 'You need to start the registration process first.'
    return response_data

def handle_myself_message(user, message):
    response_data = {}
    if message.lower().startswith('myself ') and user.is_registered:
        description = message.split(' ', 1)[1]

        user_description, created = UserDescription.objects.get_or_create(user=user)
        user_description.description_text = description
        user_description.save()

        response_data['status'] = f"You are now registered for dating. " \
                                   "To search for a MPENZI, SMS match#age#town to 22141 and meet the person of your dreams. " \
                                   "E.g., match#23-25#Nairobi"
    elif message.lower().startswith('myself ') and not user.is_registered:
        response_data['status'] = 'You need to start the registration process first.'
    return response_data

def handle_match_message(user, message):
    response_data = {}
    if message.lower().startswith('match#') and user.is_registered:
        try:
            _, age_range, county = message.split('#')
            min_age, max_age = map(int, age_range.split('-'))
        except ValueError:
            return {"status": "Invalid format. Please provide information in the format 'match#age_range#county'"}, 400

        # Gender filtering logic
        user_gender = user.profile.gender.lower().strip()

        if user_gender == 'female':
            gender_filter = 'male'
            gender_display = 'gentlemen'
            gender_type = 'man'
        elif user_gender == 'male':
            gender_filter = 'female'
            gender_display = 'ladies'
            gender_type = 'lady'
        else:
            return {"status": "Your gender preference is not recognized. To register SMS start#name#age#gender#county#town to 22141."}, 400

        matching_users = UserProfile.objects.filter(
            age__gte=min_age,
            age__lte=max_age,
            county__iexact=county,
            gender__iexact=gender_filter,
            user__is_registered=True
        )

        matching_users_count = matching_users.count()

        response_data['status'] = f"We have {matching_users_count} {gender_display} who match your choice! "

        if matching_users_count > 0:
            response_data['status'] += f"To get more details about a {gender_type}, SMS the match number e.g., 0722010203 to 22141"

        ReceivedMessage.objects.create(user=user, message=message)

        if matching_users_count > 0:
            first_three_matches = matching_users[:3]
            if first_three_matches:
                first_three_response = "Here are the first three matches: "
                for match in first_three_matches:
                    match_info = f"Name: {match.name}, Age: {match.age}, Phone Number: {match.user.phone_number}"
                    first_three_response += f"{match_info} "
            else:
                first_three_response = "There are no matches available at the moment."

            response_data_first_three = {'status': first_three_response}

            displayed_matches_key = f"displayed_matches_{user.id}"
            displayed_matches = cache.get(displayed_matches_key, [])
            displayed_matches.extend([match.id for match in first_three_matches])
            cache.set(displayed_matches_key, displayed_matches)

            return [response_data, response_data_first_three]

        return {"status": "There are no matches available at the moment. Try later!"}

    return {"status": response_data.get('status', "Invalid request")}

def handle_next_message(user):
    response_data = {}

    if user.is_registered:
        displayed_matches_key = f"displayed_matches_{user.id}"
        displayed_matches = cache.get(displayed_matches_key, [])

        user_gender = user.profile.gender.lower().strip()

        remaining_matches = UserProfile.objects.filter(
            user__is_registered=True,
            gender__iexact='female' if user_gender == 'male' else 'male'
        ).exclude(
            user_id=user.id
        ).exclude(
            id__in=displayed_matches
        )

        if len(remaining_matches) > 0:
            num_display = min(3, len(remaining_matches))
            next_matches = remaining_matches[:num_display]

            response_data['status'] = "Here are the next matches: "
            for match in next_matches:
                match_info = f"Name: {match.name}, Age: {match.age}, Phone Number: {match.user.phone_number}"
                response_data['status'] += f"{match_info} "
                displayed_matches.append(match.id)

            cache.set(displayed_matches_key, displayed_matches)
        else:
            response_data['status'] = "There are no more matches available at the moment. Try again later."

    else:
        response_data['status'] = "There are no matches available at the moment. Try again later."

    return response_data

def handle_digit_message(user, message):
    response_data = {}
    if message.isdigit():
        match_phone_number = message.zfill(10)
        match_profile = UserProfile.objects.filter(user__phone_number=match_phone_number).first()

        if match_profile:
            user_details = UserDetails.objects.filter(user=match_profile.user).first()
            if user_details:
                level_of_education = user_details.level_of_education
                profession = user_details.profession
                marital_status = user_details.marital_status
                religion = user_details.religion
                ethnicity = user_details.ethnicity
            else:
                level_of_education = "No education level available."
                profession = "Profession not available."
                marital_status = "Marital status not available."
                religion = "Religion not available."
                ethnicity = "Ethnicity not available."

            response_data['status'] = f"{match_profile.name} aged {match_profile.age}, {match_profile.county} County, {match_profile.town} town, " \
                                      f"{level_of_education}, {profession}, {marital_status}, " \
                                      f"{religion}, {ethnicity}. Send DESCRIBE {match_phone_number} to get more details about {match_profile.name}."

            # Cache the match ID and user ID for interest
            cache.set(f"match_user_{match_profile.user.id}_interested_in_{user.id}", True)
            cache.set(f"user_{user.id}_interested_in_match_{match_profile.user.id}", True)

            # Sending a message to the match profile user
            send_interest_message(match_profile.user, user.profile.name, user.profile.age, user.profile.county, user)

            ReceivedMessage.objects.create(user=user, message=message)

    return response_data

def send_interest_message(match_user, user_profile_name, user_profile_age, user_profile_county, user):
    # Fetch the user profile related to match_user
    match_user_profile = match_user.profile if hasattr(match_user, 'profile') else None

    if match_user_profile:
        # Compose the message for the match user using the UserProfile data
        message_body = f"Hi {match_user_profile.name}, {user_profile_name} is interested in you and requested your details. " \
                       f"They are aged {user_profile_age} and based in {user_profile_county}. Would you like to know more about them? " \
                       f"Reply YES to 22141."

        # Fetch the UserProfile instance associated with the user
        user_profile = user.profile if hasattr(user, 'profile') else None

        if user_profile:
            # Create a message for the match user in the system
            # Ensure the receiver is a UserProfile instance
            Message.objects.create(sender=user_profile, receiver=match_user_profile, message=message_body)

def handle_describe_message(user, message):
    response_data = {}
    
    try:
        if message.lower().startswith('describe') and len(message.split()) == 2 and user.is_registered:
            _, match_phone_number = message.split()
            match_phone_number = match_phone_number.strip()

            match_profile = UserProfile.objects.filter(user__phone_number=match_phone_number).first()

            if match_profile:
                user_description = UserDescription.objects.filter(user=match_profile.user).first()
                if user_description:
                    match_description = user_description.description_text
                else:
                    match_description = "No description available."

                response_data['status'] = f"{match_profile.name} describes themselves as  {match_description}"
                
            else:
                response_data['status'] = "No matching profile found."
        else:
            response_data['status'] = "Invalid request or user is not registered."
    except Exception as e:
        response_data['status'] = "An error occurred while processing your request."

    return response_data

def handle_yes_message(user, message):
    response_data = {}
    
    try:
        if message.lower() == 'yes' and user.is_registered:
            interested_match_id = None
            match_cache_keys = [key for key in cache._cache.keys() if key.startswith('displayed_matches_')]

            for key in match_cache_keys:
                displayed_matches = cache.get(key)
                if displayed_matches and user.id in key:
                    interested_match_id = next((match_id for match_id in displayed_matches if match_id != user.id), None)
                    break

            if interested_match_id:
                matched_profile = UserProfile.objects.filter(user__id=interested_match_id).first()
                match_interested_user = cache.get(f"match_user_{matched_profile.user.id}_interested_in_{user.id}", False)

                if matched_profile and match_interested_user:
                    # Fetch details of the profile that user showed interest in
                    matched_details = UserDetails.objects.filter(user=matched_profile.user).first()
                    if matched_details:
                        level_of_education = matched_details.level_of_education
                        profession = matched_details.profession
                        marital_status = matched_details.marital_status
                        religion = matched_details.religion
                        ethnicity = matched_details.ethnicity
                    else:
                        level_of_education = "No education level available."
                        profession = "Profession not available."
                        marital_status = "Marital status not available."
                        religion = "Religion not available."
                        ethnicity = "Ethnicity not available."

                    response_data['status'] = f"{matched_profile.name} aged {matched_profile.age}, {matched_profile.county} County, {matched_profile.town} town, " \
                                              f"{level_of_education}, {profession}, {marital_status}, " \
                                              f"{religion}, {ethnicity}. Send DESCRIBE {matched_profile.user.phone_number} to get more details about {matched_profile.name}"
                else:
                    response_data['status'] = "Unable to find a matching profile or match interest not found."
            else:
                response_data['status'] = "No interested match found for the user."
        else:
            response_data['status'] = "Invalid request or user is not registered."
    except Exception as e:
        response_data['status'] = "An error occurred while processing your request."

    return response_data