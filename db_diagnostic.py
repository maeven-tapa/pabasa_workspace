#!/usr/bin/env python
"""
Diagnostic script to verify database connections and data flow for sections/classes.
Run this from the project root: python db_diagnostic.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
django.setup()

from pabasa_app.models import User, Section
from django.db import connection

def test_database_connection():
    """Test if database connection works"""
    print("\n" + "="*60)
    print("TEST 1: Database Connection")
    print("="*60)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            print("✓ Database connection successful")
            print(f"Database: {connection.settings_dict['NAME']}")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False
    return True

def test_section_table():
    """Test if Section table exists and has data"""
    print("\n" + "="*60)
    print("TEST 2: Section Table Status")
    print("="*60)
    try:
        sections = Section.objects.all()
        print(f"✓ Section table accessible")
        print(f"  Total sections in database: {sections.count()}")
        
        if sections.exists():
            active_sections = sections.filter(is_active=True)
            print(f"  Active sections: {active_sections.count()}")
            print(f"  Inactive sections: {sections.filter(is_active=False).count()}")
            
            # Show sample section
            sample = sections.first()
            print(f"\n  Sample section details:")
            print(f"    Class Code: {sample.class_code}")
            print(f"    Class Name: {sample.class_name}")
            print(f"    Teacher ID: {sample.teacher_id}")
            print(f"    Students JSON (raw): {sample.students}")
            print(f"    Students count (via method): {sample.get_student_count()}")
            print(f"    Is Active: {sample.is_active}")
        else:
            print("  ⚠ No sections found in database")
    except Exception as e:
        print(f"✗ Error accessing Section table: {e}")
        return False
    return True

def test_section_methods():
    """Test if Section model methods work correctly"""
    print("\n" + "="*60)
    print("TEST 3: Section Model Methods")
    print("="*60)
    try:
        sections = Section.objects.filter(is_active=True)
        if not sections.exists():
            print("⚠ No active sections to test with")
            return True
        
        section = sections.first()
        print(f"Testing with section: {section.class_code}")
        
        # Test get_enrolled_students
        try:
            enrolled = section.get_enrolled_students(active_only=True)
            print(f"✓ get_enrolled_students() works: {len(enrolled)} active students")
        except Exception as e:
            print(f"✗ get_enrolled_students() failed: {e}")
        
        # Test has_student with a sample student
        students = User.objects.filter(role='student').first()
        if students:
            try:
                has_student = section.has_student(students, active_only=True)
                print(f"✓ has_student() works: Student '{students.custom_id}' enrolled: {has_student}")
            except Exception as e:
                print(f"✗ has_student() failed: {e}")
        
        # Test get_student_count
        try:
            count = section.get_student_count()
            print(f"✓ get_student_count() works: {count} active students")
        except Exception as e:
            print(f"✗ get_student_count() failed: {e}")
    
    except Exception as e:
        print(f"✗ Error testing Section methods: {e}")
        return False
    return True

def test_student_section_relationship():
    """Test the relationship between students and sections"""
    print("\n" + "="*60)
    print("TEST 4: Student-Section Relationship")
    print("="*60)
    try:
        students = User.objects.filter(role='student')
        print(f"Total students in database: {students.count()}")
        
        if students.exists():
            sample_student = students.first()
            print(f"\nTesting with student: {sample_student.custom_id}")
            
            # Check tags
            tags = sample_student.tags or []
            print(f"  User tags: {tags}")
            print(f"  Tag count: {len(tags)}")
            
            # Find sections this student is in
            enrolled_sections = []
            sections = Section.objects.filter(is_active=True)
            for section in sections:
                if section.has_student(sample_student, active_only=True):
                    enrolled_sections.append(section)
            
            print(f"  Sections enrolled in: {len(enrolled_sections)}")
            if enrolled_sections:
                for section in enrolled_sections:
                    print(f"    - {section.class_code}: {section.class_name}")
            else:
                print(f"    (None)")
        else:
            print("  ⚠ No students found")
    except Exception as e:
        print(f"✗ Error checking student-section relationship: {e}")
        return False
    return True

def test_view_context():
    """Test if the dashboard context function works"""
    print("\n" + "="*60)
    print("TEST 5: Dashboard Context Generation")
    print("="*60)
    try:
        from pabasa_app.views import _dashboard_context
        from django.test import RequestFactory
        
        students = User.objects.filter(role='student')
        if not students.exists():
            print("⚠ No students found to test with")
            return True
        
        student = students.first()
        print(f"Testing context generation for student: {student.custom_id}")
        
        # Create a mock request
        factory = RequestFactory()
        request = factory.get('/dashboard/')
        request.session = {
            'user_id': student.id,
            'custom_id': student.custom_id,
            'user_role': 'student',
            'first_name': student.first_name,
            'last_name': student.last_name,
            'email': student.email,
        }
        
        context = _dashboard_context(request, nav_role='student')
        
        print(f"✓ Context generated successfully")
        print(f"  Joined classes in context: {len(context.get('joined_classes', []))}")
        
        if context.get('joined_classes'):
            for cls in context['joined_classes']:
                print(f"    - {cls['code']}: {cls['name']}")
        else:
            print(f"    (None)")
    
    except Exception as e:
        print(f"✗ Error testing dashboard context: {e}")
        import traceback
        traceback.print_exc()
        return False
    return True

def test_database_raw_query():
    """Test raw database queries"""
    print("\n" + "="*60)
    print("TEST 6: Raw Database Queries")
    print("="*60)
    try:
        with connection.cursor() as cursor:
            # Check if sections table exists
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_name = 'sections'
            """)
            exists = cursor.fetchone()[0] > 0
            print(f"✓ Sections table exists: {exists}")
            
            if exists:
                # Get all sections
                cursor.execute("SELECT id, class_code, class_name, teacher_id, is_active, students FROM sections LIMIT 5")
                columns = [col[0] for col in cursor.description]
                print(f"\n  First 5 sections (columns: {columns}):")
                for row in cursor.fetchall():
                    print(f"    ID: {row[0]}, Code: {row[1]}, Name: {row[2]}, Active: {row[4]}")
                    if row[5]:  # students JSON
                        print(f"      Students JSON: {row[5]}")
    
    except Exception as e:
        print(f"✗ Error with raw queries: {e}")
        import traceback
        traceback.print_exc()
        return False
    return True

def main():
    print("\n" + "="*60)
    print("PABASA DATABASE DIAGNOSTIC")
    print("="*60)
    
    all_pass = True
    all_pass &= test_database_connection()
    all_pass &= test_section_table()
    all_pass &= test_database_raw_query()
    all_pass &= test_section_methods()
    all_pass &= test_student_section_relationship()
    all_pass &= test_view_context()
    
    print("\n" + "="*60)
    if all_pass:
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED - See details above")
    print("="*60 + "\n")

if __name__ == '__main__':
    main()
