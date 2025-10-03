from django.contrib.auth.models import AnonymousUser
from rest_framework import authentication
from firebase_admin import auth
from django.conf import settings

class FirebaseAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION")
        if not auth_header:
            return None

        try:
            id_token = auth_header.split(" ").pop()
            decoded_token = auth.verify_id_token(id_token)
            return (self.get_user(decoded_token), None)
        except Exception as e:
            return None

    def get_user(self, decoded_token):
        from users.models import User
        try:
            uid = decoded_token.get('uid')
            return User.objects.get(firebase_uid=uid)
        except User.DoesNotExist:
            return AnonymousUser()