from dj_rest_auth.jwt_auth import unset_jwt_cookies
from django.http.response import HttpResponseRedirect
from rest_framework_simplejwt.views import TokenRefreshView, TokenObtainPairView
from allauth.account.models import EmailAddress
from dj_rest_auth.views import LoginView
from django.contrib import messages
from rest_framework.views import APIView
from .models import User
from rest_framework import generics, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from .serializers import *
from rest_framework.response import Response
from rest_framework import status
from allauth.account.adapter import get_adapter
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from django.contrib.auth import logout as django_logout
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.utils import datetime_from_epoch
from dj_rest_auth.views import PasswordResetConfirmView
from rest_framework.decorators import api_view, permission_classes
from posts.models import Post
from django.shortcuts import get_object_or_404


class CustomLoginView(LoginView):
    serializer_class = CustomLoginSerializer

    def get_response(self):
        serializer_class = self.get_response_serializer()
        data = {
            'user': self.user,
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
        }

        serializer = serializer_class(
            instance=data,
            context=self.get_serializer_context(),
        )

        response = Response(serializer.data, status=status.HTTP_200_OK)
        cookie_max_age = self.refresh_token.lifetime.total_seconds()
        response.set_cookie(
            'refresh_token', response.data['refresh_token'], max_age=cookie_max_age, httponly=True)

        return response


class ResendEmailView(generics.GenericAPIView):
    serializer_class = EmailResendSerializer
    permission_classes = [AllowAny, ]

    def _action_send(self, request, *args, **kwargs):
        email = request.POST['email']
        email_address = EmailAddress.objects.get(email=email)
        get_adapter(request).add_message(
            request,
            messages.INFO,
            'account/messages/' 'email_confirmation_sent.txt',
            {'email': email},
        )
        email_address.send_confirmation(request)

    def post(self, request):
        data = request.data
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        self._action_send(request)
        return Response({'success': '이메일이 전송되었습니다.'}, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [AllowAny, ]

    def get_token(self, request):
        if request.COOKIES != {}:
            token = request.COOKIES['refresh_token']
            return token
        return ""

    def logout(self, request, token):
        django_logout(request)
        response = Response(
            {'success': 'Successfully logged out.'},
            status=status.HTTP_200_OK,
        )
        try:
            t = RefreshToken(token)
            t.blacklist()
            unset_jwt_cookies(response)
            return response
        except:
            response.data = {'error': 'Logout Failed.'}
            response.status_code = status.HTTP_400_BAD_REQUEST
            return response

    def get(self, request):
        res = self.get_token(request)
        if res != "":
            return self.logout(request, res)
        return Response({'error': 'Logout Failed.'})


class LogoutAllView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        tokens = OutstandingToken.objects.filter(user_id=request.user.id)
        for token in tokens:
            t, _ = BlacklistedToken.objects.get_or_create(token=token)
        return Response(status=status.HTTP_205_RESET_CONTENT)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = {
            'user': serializer.data,
        }
        return Response(data)


class CookieTokenObtainPairView(TokenObtainPairView):
    permission_classes = [AllowAny, ]

    def finalize_response(self, request, response, *args, **kwargs):
        if response.data.get('refresh'):
            cookie_max_age = 3600 * 24 * 1  # 1 day
            response.set_cookie(
                'refresh_token', response.data['refresh'], max_age=cookie_max_age, httponly=True)
            del response.data['refresh']
        return super().finalize_response(request, response, *args, **kwargs)


class CookieTokenRefreshView(TokenRefreshView):
    serializer_class = CookieTokenRefreshSerializer
    permission_classes = [AllowAny, ]

    def finalize_response(self, request, response, *args, **kwargs):
        if response.data.get('refresh'):
            token = RefreshToken(response.data.get('refresh'))
            jti = token[api_settings.JTI_CLAIM]
            exp = token['exp']

            user_id = request.data['user_id']
            user = User.objects.get(pk=user_id)

            OutstandingToken.objects.create(
                user=user,
                jti=jti,
                token=str(token),
                created_at=token.current_time,
                expires_at=datetime_from_epoch(exp),
            )
            cookie_max_age = 3600 * 24 * 1  # 1 day
            response.set_cookie(
                'refresh_token', response.data['refresh'], max_age=cookie_max_age, httponly=True)
            del response.data['refresh']
        return super().finalize_response(request, response, *args, **kwargs)


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    def get(self, request, uidb64, token):
        return HttpResponseRedirect(f'http://localhost:3000/accounts/password-reset?uidb64={uidb64}&token={token}')


@api_view(['get', 'post', 'delete'])
@permission_classes((IsAuthenticated,))
def bookmark(request, post_id=None):
    if request.method == 'GET':  # 사용자 북마크 리스트
        data = BookMarkSerializer(request.user).data
        return Response(data, status=status.HTTP_200_OK)
    else:  # 북마크 생성/삭제
        post = get_object_or_404(Post, pk=post_id)
        if post.bookmarks.filter(id=request.user.id).exists():
            post.bookmarks.remove(request.user)
        else:
            post.bookmarks.add(request.user)
        return Response('success', status=status.HTTP_200_OK)
