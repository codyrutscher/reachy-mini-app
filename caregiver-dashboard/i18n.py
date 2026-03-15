"""Internationalization — simple translation system for the dashboard.

Supports: English, Spanish, French, German, Italian, Portuguese.
Usage: from i18n import t; t('dashboard', lang='es')"""

TRANSLATIONS = {
    "en": {
        "dashboard": "Dashboard", "patients": "Patients", "medications": "Medications",
        "schedule": "Schedule", "history": "History", "reports": "Reports",
        "activity": "Activity", "facilities": "Facilities", "family": "Family",
        "settings": "Settings", "login": "Login", "logout": "Logout",
        "connected": "Connected", "reconnecting": "Reconnecting...",
        "send": "Send", "cancel": "Cancel", "save": "Save", "delete": "Delete",
        "alerts": "Alerts", "no_alerts": "No alerts yet",
        "conversation": "Live Conversation", "message_placeholder": "Type a message...",
        "emergency_sos": "Emergency SOS", "current_mood": "Current Mood",
        "heart_rate": "Heart Rate", "blood_pressure": "Blood Pressure",
        "temperature": "Temperature", "oxygen": "Oxygen Level",
        "shift_handoff": "Shift Handoff", "create_handoff": "Create Handoff",
        "family_portal": "Family Portal", "send_message": "Send Message",
        "vitals": "Vitals", "mood_chart": "Mood Chart",
        "med_adherence": "Medication Adherence", "caregiver_notes": "Caregiver Notes",
    },
    "es": {
        "dashboard": "Panel", "patients": "Pacientes", "medications": "Medicamentos",
        "schedule": "Horario", "history": "Historial", "reports": "Informes",
        "activity": "Actividad", "facilities": "Instalaciones", "family": "Familia",
        "settings": "Configuración", "login": "Iniciar sesión", "logout": "Cerrar sesión",
        "connected": "Conectado", "reconnecting": "Reconectando...",
        "send": "Enviar", "cancel": "Cancelar", "save": "Guardar", "delete": "Eliminar",
        "alerts": "Alertas", "no_alerts": "Sin alertas",
        "conversation": "Conversación en vivo", "message_placeholder": "Escribe un mensaje...",
        "emergency_sos": "SOS de emergencia", "current_mood": "Estado de ánimo",
        "heart_rate": "Frecuencia cardíaca", "blood_pressure": "Presión arterial",
        "temperature": "Temperatura", "oxygen": "Nivel de oxígeno",
        "shift_handoff": "Cambio de turno", "create_handoff": "Crear informe",
        "family_portal": "Portal familiar", "send_message": "Enviar mensaje",
        "vitals": "Signos vitales", "mood_chart": "Gráfico de ánimo",
        "med_adherence": "Adherencia a medicamentos", "caregiver_notes": "Notas del cuidador",
    },
    "fr": {
        "dashboard": "Tableau de bord", "patients": "Patients", "medications": "Médicaments",
        "schedule": "Horaire", "history": "Historique", "reports": "Rapports",
        "activity": "Activité", "facilities": "Établissements", "family": "Famille",
        "settings": "Paramètres", "login": "Connexion", "logout": "Déconnexion",
        "connected": "Connecté", "reconnecting": "Reconnexion...",
        "send": "Envoyer", "cancel": "Annuler", "save": "Enregistrer", "delete": "Supprimer",
        "alerts": "Alertes", "no_alerts": "Aucune alerte",
        "conversation": "Conversation en direct", "message_placeholder": "Tapez un message...",
        "emergency_sos": "SOS d'urgence", "current_mood": "Humeur actuelle",
        "heart_rate": "Fréquence cardiaque", "blood_pressure": "Pression artérielle",
        "temperature": "Température", "oxygen": "Niveau d'oxygène",
        "shift_handoff": "Relève de poste", "create_handoff": "Créer un rapport",
        "family_portal": "Portail familial", "send_message": "Envoyer un message",
        "vitals": "Signes vitaux", "mood_chart": "Graphique d'humeur",
        "med_adherence": "Observance médicamenteuse", "caregiver_notes": "Notes du soignant",
    },
    "de": {
        "dashboard": "Übersicht", "patients": "Patienten", "medications": "Medikamente",
        "schedule": "Zeitplan", "history": "Verlauf", "reports": "Berichte",
        "activity": "Aktivität", "facilities": "Einrichtungen", "family": "Familie",
        "settings": "Einstellungen", "login": "Anmelden", "logout": "Abmelden",
        "connected": "Verbunden", "reconnecting": "Verbindung wird hergestellt...",
        "send": "Senden", "cancel": "Abbrechen", "save": "Speichern", "delete": "Löschen",
        "alerts": "Warnungen", "no_alerts": "Keine Warnungen",
        "conversation": "Live-Gespräch", "message_placeholder": "Nachricht eingeben...",
        "emergency_sos": "Notfall-SOS", "current_mood": "Aktuelle Stimmung",
        "heart_rate": "Herzfrequenz", "blood_pressure": "Blutdruck",
        "temperature": "Temperatur", "oxygen": "Sauerstoffgehalt",
        "shift_handoff": "Schichtübergabe", "create_handoff": "Übergabe erstellen",
        "family_portal": "Familienportal", "send_message": "Nachricht senden",
        "vitals": "Vitalzeichen", "mood_chart": "Stimmungsdiagramm",
        "med_adherence": "Medikamententreue", "caregiver_notes": "Pflegenotizen",
    },
}

_current_lang = "en"


def set_language(lang):
    global _current_lang
    if lang in TRANSLATIONS:
        _current_lang = lang


def get_language():
    return _current_lang


def t(key, lang=None):
    """Translate a key to the current or specified language."""
    lang = lang or _current_lang
    strings = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    return strings.get(key, TRANSLATIONS["en"].get(key, key))


def get_all_translations(lang=None):
    """Get all translations for a language (for JS injection)."""
    lang = lang or _current_lang
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"])


def available_languages():
    return list(TRANSLATIONS.keys())
