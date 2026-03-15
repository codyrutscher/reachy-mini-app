"""Tests for the reminder system."""

import pytest
import json
import os


class TestReminderManager:

    def test_add_medication(self, reminder_manager):
        result = reminder_manager.add_medication("Aspirin", ["08:00", "20:00"])
        assert "aspirin" in result.lower()
        assert len(reminder_manager.medications) == 1
        assert reminder_manager.medications[0]["name"] == "Aspirin"
        assert reminder_manager.medications[0]["times"] == ["08:00", "20:00"]

    def test_add_multiple_medications(self, reminder_manager):
        reminder_manager.add_medication("Aspirin", ["08:00"])
        reminder_manager.add_medication("Metformin", ["12:00", "18:00"])
        assert len(reminder_manager.medications) == 2

    def test_remove_medication(self, reminder_manager):
        reminder_manager.add_medication("Aspirin", ["08:00"])
        result = reminder_manager.remove_medication("Aspirin")
        assert "removed" in result.lower()
        assert len(reminder_manager.medications) == 0

    def test_remove_nonexistent_medication(self, reminder_manager):
        result = reminder_manager.remove_medication("NotReal")
        assert "don't have" in result.lower()

    def test_list_reminders_empty(self, reminder_manager):
        result = reminder_manager.list_reminders()
        assert "don't have any" in result.lower()

    def test_list_reminders_with_data(self, reminder_manager):
        reminder_manager.add_medication("Aspirin", ["08:00"])
        reminder_manager.add_appointment("Dr. Smith", "2026-04-01 14:00")
        result = reminder_manager.list_reminders()
        assert "aspirin" in result.lower()
        assert "dr. smith" in result.lower()

    def test_persistence(self, reminder_manager, tmp_path, monkeypatch):
        """Data should persist to disk and reload."""
        import reminders
        reminder_manager.add_medication("TestMed", ["09:00"])
        # Create a new manager pointing to same file
        rm2 = reminders.ReminderManager()
        assert len(rm2.medications) == 1
        assert rm2.medications[0]["name"] == "TestMed"

    def test_add_appointment(self, reminder_manager):
        result = reminder_manager.add_appointment("Dentist", "2026-05-15 10:00")
        assert "dentist" in result.lower()
        assert len(reminder_manager.appointments) == 1

    def test_reminder_callback(self, reminder_manager):
        """The on_reminder callback should be stored."""
        fired = []
        rm = reminder_manager
        rm.on_reminder = lambda msg: fired.append(msg)
        rm._fire("Test reminder")
        assert len(fired) == 1
        assert fired[0] == "Test reminder"
