from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import User
from django.contrib.auth.hashers import make_password
from django.utils.crypto import get_random_string
from .serializers import CustomTokenObtainPairSerializer, UserRegistrationSerializer
import json
from django.db import models

class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class RegisterView(APIView):
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            # Automatically assign user to department if specified
            department_id = request.data.get('department')
            if department_id:
                try:
                    from timetable.models import Department, UserDepartment
                    department = Department.objects.get(id=department_id)
                    
                    # Check if this is the first user in the department
                    existing_users = UserDepartment.objects.filter(department=department, is_active=True).count()
                    
                    # First user becomes ADMIN, others become TEACHER
                    role = 'ADMIN' if existing_users == 0 else 'TEACHER'
                    
                    # Create user-department relationship
                    UserDepartment.objects.create(
                        user=user,
                        department=department,
                        role=role
                    )
                except Department.DoesNotExist:
                    pass  # Department doesn't exist, skip assignment
                except Exception as e:
                    print(f"Error assigning user to department: {e}")
            
            return Response({
                'message': 'User created successfully',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                }
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': getattr(user, 'role', 'TEACHER')
        }, status=status.HTTP_200_OK)

    def delete(self, request):
        try:
            user = request.user
            user_id = user.id
            username = user.username
            user.delete()
            return Response({
                'message': 'Account deleted successfully',
                'id': user_id,
                'username': username
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': f'Failed to delete account: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

class ForgotPasswordView(APIView):
    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(email=email)
            # Generate a simple reset token (in real app, this would be more secure)
            reset_token = get_random_string(32)
            
            # Store the reset token in user's session or temporary storage
            # For simplicity, we'll store it in a JSON field or use a simple approach
            # In production, you might want to use Redis or database table for tokens
            
            # For now, we'll create a simple token that can be validated
            # Store token in user's last_name temporarily (not ideal but simple for demo)
            user.last_name = f"RESET_TOKEN:{reset_token}"
            user.save()
            
            return Response({
                'message': 'Password reset initiated',
                'reset_token': reset_token,
                'email': email,
                'user_info': {
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                }
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response({'error': 'User with this email does not exist'}, status=status.HTTP_404_NOT_FOUND)

class ResetPasswordView(APIView):
    def post(self, request):
        reset_token = request.data.get('reset_token')
        new_password = request.data.get('new_password')
        email = request.data.get('email')
        
        if not all([reset_token, new_password, email]):
            return Response({'error': 'All fields are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(email=email)
            
            # Check if the reset token matches
            if user.last_name == f"RESET_TOKEN:{reset_token}":
                # Update password
                user.password = make_password(new_password)
                user.last_name = ""  # Clear the reset token
                
                # Force save and refresh
                user.save(force_update=True)
                user.refresh_from_db()
                
                # Verify password was actually changed
                password_verified = user.check_password(new_password)
                
                # Return user info for debugging
                return Response({
                    'message': 'Password reset successful',
                    'password_verified': password_verified,
                    'user_info': {
                        'username': user.username,
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name
                    }
                }, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Invalid reset token'}, status=status.HTTP_400_BAD_REQUEST)
                
        except User.DoesNotExist:
            return Response({'error': 'User with this email does not exist'}, status=status.HTTP_404_NOT_FOUND)


class UsersListView(APIView):
    """View to list users for shared access functionality"""
    
    def get(self, request):
        try:
            # Get current user's department
            from timetable.models import UserDepartment
            current_user_dept = None
            
            try:
                user_dept = UserDepartment.objects.get(user=request.user, is_active=True)
                current_user_dept = user_dept.department
            except UserDepartment.DoesNotExist:
                pass
            
            # Get all users (excluding current user)
            users = User.objects.exclude(id=request.user.id).filter(is_active=True)
            
            # Filter by department if user has one
            if current_user_dept:
                # Include only users in the same department
                users = users.filter(
                    models.Q(userdepartment__department=current_user_dept)
                ).distinct()
            
            user_list = []
            for user in users:
                user_data = {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name or '',
                    'last_name': user.last_name or '',
                    'full_name': f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username
                }
                user_list.append(user_data)
            
            return Response(user_list, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to fetch users: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PublicDepartmentsView(APIView):
    """Public endpoint to list departments for signup"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        try:
            from timetable.models import Department
            # Only return departments that actually exist and are active
            departments = Department.objects.filter(
                is_active=True
            ).exclude(
                name__isnull=True
            ).exclude(
                name__exact=''
            ).order_by('name')
            
            department_list = []
            for dept in departments:
                dept_data = {
                    'id': dept.id,
                    'name': dept.name,
                    'code': dept.code,
                    'description': dept.description or ''
                }
                department_list.append(dept_data)
            
            return Response(department_list, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to fetch departments: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )