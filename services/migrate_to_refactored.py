"""
Migration Script: Transition from Original Pitboss to Refactored Version

This script helps transition existing code to use the new refactored pitboss
while maintaining backwards compatibility.
"""

import os
import shutil
from datetime import datetime


def backup_original():
    """Backup the original pitboss.py file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    original = "services/pitboss.py"
    backup = f"services/pitboss_backup_{timestamp}.py"
    
    if os.path.exists(original):
        shutil.copy2(original, backup)
        print(f"✓ Backed up original to {backup}")
        return backup
    else:
        print("✗ Original pitboss.py not found")
        return None


def create_compatibility_wrapper():
    """Create a compatibility wrapper for existing imports."""
    wrapper_content = '''"""
Pitboss - Compatibility Wrapper for Refactored System

This module provides backwards compatibility for existing code
while using the new refactored implementation underneath.
"""

# Import everything from the refactored version
from services.pitboss_supervisor import Pitboss, PitbossSupervisor
from services.tools import ToolRegistry
from services.context_builder import ContextBuilder
from services.config import get_config

# For backwards compatibility, also import the legacy classes
# These are now implemented in the refactored modules
LanguageAgent = None  # Now part of SqlPitbossTool
ToolAgent = None      # Now part of DataTableTool  
CallbackAgent = None  # Now part of WebSocket handling in Supervisor

# Helper functions that were in the original
def summarize_sql_to_rule_id(sql: str) -> str:
    """Legacy helper - now in PitbossSupervisor._generate_rule_id"""
    supervisor = PitbossSupervisor(None)
    return supervisor._generate_rule_id(sql)


def _make_results_table_name(protocol_id: str, rule_id: str) -> str:
    """Legacy helper - now in DataTableTool._make_table_name"""
    from services.tools import DataTableTool
    tool = DataTableTool(None)
    return tool._make_table_name(protocol_id, rule_id)


def _strip_to_select(sql: str) -> str:
    """Legacy helper - now in DataTableTool._strip_to_select"""
    from services.tools import DataTableTool
    tool = DataTableTool(None)
    return tool._strip_to_select(sql)


# Export the main Pitboss class (which is backwards compatible)
__all__ = ['Pitboss', 'PitbossSupervisor']
'''
    
    with open("services/pitboss.py.new", "w") as f:
        f.write(wrapper_content)
    
    print("✓ Created compatibility wrapper")
    return "services/pitboss.py.new"


def update_imports_in_file(filepath, dry_run=True):
    """Update imports in a Python file to use refactored modules."""
    
    replacements = [
        # Update direct pitboss imports
        ("from services.pitboss import Pitboss", 
         "from services.pitboss_supervisor import Pitboss"),
        
        ("from pitboss import Pitboss",
         "from services.pitboss_supervisor import Pitboss"),
         
        # Update agent imports (if any)
        ("from services.pitboss import LanguageAgent",
         "from services.tools import SqlPitbossTool as LanguageAgent"),
         
        ("from services.pitboss import ToolAgent",
         "from services.tools import DataTableTool as ToolAgent"),
    ]
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        original_content = content
        for old, new in replacements:
            if old in content:
                content = content.replace(old, new)
                print(f"  → Updated: {old} -> {new}")
        
        if content != original_content:
            if not dry_run:
                with open(filepath, 'w') as f:
                    f.write(content)
                print(f"  ✓ Updated {filepath}")
            else:
                print(f"  [DRY RUN] Would update {filepath}")
            return True
        else:
            print(f"  ℹ No changes needed in {filepath}")
            return False
            
    except Exception as e:
        print(f"  ✗ Error processing {filepath}: {e}")
        return False


def find_files_using_pitboss():
    """Find all Python files that import pitboss."""
    files_to_check = [
        "services/api.py",
        "services/server.py",
        "services/combined_app.py",
        "services/pitboss-test.py",
        "services/pitboss_agentic_dsl_runner.py"
    ]
    
    files_using_pitboss = []
    for filepath in files_to_check:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                content = f.read()
                if 'pitboss' in content.lower() or 'Pitboss' in content:
                    files_using_pitboss.append(filepath)
    
    return files_using_pitboss


def run_migration(dry_run=True):
    """Run the complete migration process."""
    print("\n" + "="*60)
    print("PITBOSS REFACTORING MIGRATION")
    print("="*60)
    
    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"\nMode: {mode}")
    print("-"*60)
    
    # Step 1: Backup original
    print("\nStep 1: Backup Original")
    backup_path = backup_original() if not dry_run else "[skipped in dry run]"
    
    # Step 2: Find files using pitboss
    print("\nStep 2: Find Files Using Pitboss")
    files = find_files_using_pitboss()
    print(f"Found {len(files)} files using pitboss:")
    for f in files:
        print(f"  • {f}")
    
    # Step 3: Update imports
    print("\nStep 3: Update Imports")
    for filepath in files:
        print(f"\nProcessing {filepath}:")
        update_imports_in_file(filepath, dry_run=dry_run)
    
    # Step 4: Create compatibility wrapper
    if not dry_run:
        print("\nStep 4: Install Compatibility Wrapper")
        wrapper_path = create_compatibility_wrapper()
        print(f"Created wrapper at: {wrapper_path}")
        print("To activate: mv services/pitboss.py.new services/pitboss.py")
    
    # Summary
    print("\n" + "="*60)
    print("MIGRATION SUMMARY")
    print("="*60)
    
    if dry_run:
        print("\n✓ Dry run complete. No files were modified.")
        print("\nTo apply changes, run:")
        print("  python services/migrate_to_refactored.py --apply")
    else:
        print("\n✓ Migration complete!")
        print("\nNext steps:")
        print("1. Review the changes")
        print("2. Test the system with: python services/pitboss-test.py")
        print("3. If everything works, remove backup files")
    
    print("\nThe refactored system provides:")
    print("  • Better separation of concerns")
    print("  • Modular tool system")
    print("  • Proper context injection (PROTOCOL → DATA → RULES)")
    print("  • Configuration management")
    print("  • Backwards compatibility")
    

if __name__ == "__main__":
    import sys
    
    # Check for --apply flag
    apply_changes = "--apply" in sys.argv
    
    # Run migration
    run_migration(dry_run=not apply_changes)