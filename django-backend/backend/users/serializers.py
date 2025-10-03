from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from rest_framework_simplejwt.exceptions import InvalidToken
from .models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password', 'password_confirm']

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match.")
        
        # Check if email already exists
        email = attrs.get('email')
        if email and User.objects.filter(email=email).exists():
            raise serializers.ValidationError({
                'email': 'A user with this email address already exists. Please use a different email or try logging in.'
            })
        
        # Check if username already exists
        username = attrs.get('username')
        if username and User.objects.filter(username=username).exists():
            raise serializers.ValidationError({
                'username': 'A user with this username already exists. Please choose a different username.'
            })
        
        return attrs

    def create(self, validated_data):
        # Remove password_confirm from validated_data
        validated_data.pop('password_confirm', None)

        # Create user with encrypted password
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            password=validated_data['password']
        )
        return user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        # Get the username (which could be email from frontend)
        username_or_email = attrs.get('username')
        password = attrs.get('password')

        if username_or_email and password:
            user = None
            user_exists = False

            # Check if it's an email format
            if '@' in username_or_email:
                try:
                    user_obj = User.objects.get(email=username_or_email)
                    user_exists = True
                    user = authenticate(username=user_obj.username, password=password)
                except User.DoesNotExist:
                    user_exists = False
            else:
                # Not an email, try as username
                try:
                    User.objects.get(username=username_or_email)
                    user_exists = True
                    user = authenticate(username=username_or_email, password=password)
                except User.DoesNotExist:
                    user_exists = False

            # Provide specific error messages
            if not user_exists:
                raise serializers.ValidationError("User doesn't exist")
            elif user_exists and not user:
                raise serializers.ValidationError("Invalid password")
            else:
                # Store the authenticated user for token generation
                self.user = user                
                # Create tokens manually
                refresh = RefreshToken.for_user(user)
                access = refresh.access_token
                
                # Add custom claims
                access['role'] = getattr(user, 'role', 'TEACHER')
                
                return {
                    'access': str(access),
                    'refresh': str(refresh),
                }

        # If we reach here, something went wrong
        raise serializers.ValidationError("Authentication failed")

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = getattr(user, 'role', 'TEACHER')  # Default role if not set
        return token