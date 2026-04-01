from django.shortcuts import render

def home(request):
    return render(request, 'pabasa_app/home.html')
