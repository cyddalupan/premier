from django.shortcuts import render

def terms_and_conditions(request):
    return render(request, 'legal/terms_and_conditions.html')

def privacy_policy(request):
    return render(request, 'legal/privacy_policy.html')