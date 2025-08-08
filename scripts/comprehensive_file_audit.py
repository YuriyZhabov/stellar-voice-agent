#!/usr/bin/env python3
"""
Comprehensive file audit script for Voice AI Agent project.
This script analyzes all files in the project and identifies testing needs.
"""

import os
import sys
import json
import yaml
import subprocess
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
from dataclasses import dataclass, field
import ast
import re
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class FileAnalysis:
    """Analysis result for a single file."""
    path: str
    file_type: str
    size: int
    lines: int
    has_tests: bool = False
    test_coverage: float = 0.0
    issues: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    complexity_score: int = 0
    security_issues: List[str] = field(default_factory=list)

@dataclass
class ProjectAudit:
    """Complete project audit results."""
    total_files: int = 0
    files_by_type: Dict[str, int] = field(default_factory=dict)
    python_files: List[FileAnalysis] = field(default_factory=list)
    config_files: List[FileAnalysis] = field(default_factory=list)
    script_files: List[FileAnalysis] = field(default_factory=list)
    doc_files: List[FileAnalysis] = field(default_factory=list)
    other_files: List[FileAnalysis] = field(default_factory=list)
    test_coverage_summary: Dict[str, Any] = field(default_factory=dict)
    issues_summary: Dict[str, int] = field(default_factory=dict)

class ComprehensiveFileAuditor:
    """Comprehensive file auditor for the Voice AI Agent project."""
    
    def __init__(self, project_root: str = "."):
        """Initialize the auditor."""
        self.project_root = Path(project_root).resolve()
        self.audit = ProjectAudit()
        
        # File type mappings
        self.file_types = {
            '.py': 'python',
            '.yaml': 'yaml',
            '.yml': 'yaml', 
            '.json': 'json',
            '.md': 'markdown',
            '.sh': 'shell',
            '.dockerfile': 'docker',
            '.env': 'environment',
            '.txt': 'text',
            '.toml': 'toml',
            '.cfg': 'config',
            '.ini': 'config'
        }
        
        # Directories to skip
        self.skip_dirs = {
            '__pycache__', '.git', '.pytest_cache', 'node_modules', 
            '.venv', 'venv', '.env', 'logs', 'data', '.kiro'
        }
        
        # Files to skip
        self.skip_files = {
            '.gitignore', '.dockerignore', 'requirements.txt', 'pyproject.toml'
        }
    
    def get_file_type(self, file_path: Path) -> str:
        """Determine file type based on extension."""
        suffix = file_path.suffix.lower()
        if suffix in self.file_types:
            return self.file_types[suffix]
        elif file_path.name.lower().startswith('dockerfile'):
            return 'docker'
        elif file_path.name.lower().startswith('makefile'):
            return 'makefile'
        else:
            return 'other'
    
    def should_skip_path(self, path: Path) -> bool:
        """Check if path should be skipped."""
        # Skip hidden files and directories
        if any(part.startswith('.') and part not in {'.env', '.env.example'} 
               for part in path.parts):
            return True
        
        # Skip specific directories
        if any(skip_dir in path.parts for skip_dir in self.skip_dirs):
            return True
        
        # Skip specific files
        if path.name in self.skip_files:
            return True
        
        return False
    
    def analyze_python_file(self, file_path: Path) -> FileAnalysis:
        """Analyze a Python file."""
        analysis = FileAnalysis(
            path=str(file_path.relative_to(self.project_root)),
            file_type='python',
            size=file_path.stat().st_size,
            lines=0
        )
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                analysis.lines = len(content.splitlines())
            
            # Parse AST for detailed analysis
            try:
                tree = ast.parse(content)
                self._analyze_ast(tree, analysis)
            except SyntaxError as e:
                analysis.issues.append(f"Syntax error: {e}")
            
            # Check for test file
            test_file_path = self._find_test_file(file_path)
            analysis.has_tests = test_file_path is not None
            
            # Security analysis
            self._analyze_security(content, analysis)
            
            # Complexity analysis
            analysis.complexity_score = self._calculate_complexity(content)
            
        except Exception as e:
            analysis.issues.append(f"Failed to analyze: {e}")
        
        return analysis
    
    def _analyze_ast(self, tree: ast.AST, analysis: FileAnalysis):
        """Analyze Python AST for functions, classes, and imports."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                analysis.functions.append(node.name)
            elif isinstance(node, ast.ClassDef):
                analysis.classes.append(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    analysis.imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    analysis.imports.append(node.module)
    
    def _find_test_file(self, file_path: Path) -> Optional[Path]:
        """Find corresponding test file."""
        # Convert src/module.py to tests/test_module.py
        relative_path = file_path.relative_to(self.project_root)
        
        # Try different test file patterns
        test_patterns = [
            self.project_root / "tests" / f"test_{file_path.stem}.py",
            self.project_root / "tests" / relative_path.parent / f"test_{file_path.stem}.py",
            self.project_root / "test" / f"test_{file_path.stem}.py",
        ]
        
        for test_path in test_patterns:
            if test_path.exists():
                return test_path
        
        return None
    
    def _analyze_security(self, content: str, analysis: FileAnalysis):
        """Analyze Python file for security issues."""
        security_patterns = [
            (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password"),
            (r'api_key\s*=\s*["\'][^"\']+["\']', "Hardcoded API key"),
            (r'secret\s*=\s*["\'][^"\']+["\']', "Hardcoded secret"),
            (r'eval\s*\(', "Use of eval() function"),
            (r'exec\s*\(', "Use of exec() function"),
            (r'subprocess\.call\([^)]*shell=True', "Shell injection risk"),
            (r'os\.system\s*\(', "OS command injection risk"),
        ]
        
        for pattern, issue in security_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                analysis.security_issues.append(issue)
    
    def _calculate_complexity(self, content: str) -> int:
        """Calculate basic complexity score."""
        complexity = 0
        
        # Count control structures
        complexity += len(re.findall(r'\bif\b', content))
        complexity += len(re.findall(r'\bfor\b', content))
        complexity += len(re.findall(r'\bwhile\b', content))
        complexity += len(re.findall(r'\btry\b', content))
        complexity += len(re.findall(r'\bexcept\b', content))
        complexity += len(re.findall(r'\bwith\b', content))
        
        return complexity
    
    def analyze_yaml_file(self, file_path: Path) -> FileAnalysis:
        """Analyze a YAML file."""
        analysis = FileAnalysis(
            path=str(file_path.relative_to(self.project_root)),
            file_type='yaml',
            size=file_path.stat().st_size,
            lines=0
        )
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                analysis.lines = len(content.splitlines())
            
            # Validate YAML syntax
            try:
                yaml.safe_load(content)
            except yaml.YAMLError as e:
                analysis.issues.append(f"YAML syntax error: {e}")
            
            # Check for common issues
            if 'password' in content.lower() and not content.startswith('#'):
                analysis.security_issues.append("Potential password in YAML")
            
        except Exception as e:
            analysis.issues.append(f"Failed to analyze: {e}")
        
        return analysis
    
    def analyze_json_file(self, file_path: Path) -> FileAnalysis:
        """Analyze a JSON file."""
        analysis = FileAnalysis(
            path=str(file_path.relative_to(self.project_root)),
            file_type='json',
            size=file_path.stat().st_size,
            lines=0
        )
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                analysis.lines = len(content.splitlines())
            
            # Validate JSON syntax
            try:
                json.loads(content)
            except json.JSONDecodeError as e:
                analysis.issues.append(f"JSON syntax error: {e}")
            
        except Exception as e:
            analysis.issues.append(f"Failed to analyze: {e}")
        
        return analysis
    
    def analyze_shell_file(self, file_path: Path) -> FileAnalysis:
        """Analyze a shell script file."""
        analysis = FileAnalysis(
            path=str(file_path.relative_to(self.project_root)),
            file_type='shell',
            size=file_path.stat().st_size,
            lines=0
        )
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                analysis.lines = len(content.splitlines())
            
            # Check for executable permission
            if not os.access(file_path, os.X_OK):
                analysis.issues.append("Script is not executable")
            
            # Check for shebang
            if not content.startswith('#!'):
                analysis.issues.append("Missing shebang line")
            
            # Check for set -e (exit on error)
            if 'set -e' not in content and 'set -euo pipefail' not in content:
                analysis.issues.append("Missing 'set -e' for error handling")
            
            # Security checks
            if re.search(r'\$\([^)]*\)', content):
                analysis.security_issues.append("Command substitution found - review for injection")
            
        except Exception as e:
            analysis.issues.append(f"Failed to analyze: {e}")
        
        return analysis
    
    def analyze_markdown_file(self, file_path: Path) -> FileAnalysis:
        """Analyze a Markdown file."""
        analysis = FileAnalysis(
            path=str(file_path.relative_to(self.project_root)),
            file_type='markdown',
            size=file_path.stat().st_size,
            lines=0
        )
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                analysis.lines = len(content.splitlines())
            
            # Check for common markdown issues
            if not content.strip():
                analysis.issues.append("Empty markdown file")
            
            # Check for broken links (basic check)
            broken_links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
            for link_text, link_url in broken_links:
                if link_url.startswith('http') and 'localhost' in link_url:
                    analysis.issues.append(f"Localhost link may not work in production: {link_url}")
            
        except Exception as e:
            analysis.issues.append(f"Failed to analyze: {e}")
        
        return analysis
    
    def analyze_file(self, file_path: Path) -> FileAnalysis:
        """Analyze a single file based on its type."""
        file_type = self.get_file_type(file_path)
        
        if file_type == 'python':
            return self.analyze_python_file(file_path)
        elif file_type == 'yaml':
            return self.analyze_yaml_file(file_path)
        elif file_type == 'json':
            return self.analyze_json_file(file_path)
        elif file_type == 'shell':
            return self.analyze_shell_file(file_path)
        elif file_type == 'markdown':
            return self.analyze_markdown_file(file_path)
        else:
            # Generic file analysis
            analysis = FileAnalysis(
                path=str(file_path.relative_to(self.project_root)),
                file_type=file_type,
                size=file_path.stat().st_size,
                lines=0
            )
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    analysis.lines = len(content.splitlines())
            except Exception as e:
                analysis.issues.append(f"Failed to read file: {e}")
            
            return analysis
    
    def run_existing_tests(self) -> Dict[str, Any]:
        """Run existing test suite and collect coverage."""
        test_results = {
            'tests_run': 0,
            'tests_passed': 0,
            'tests_failed': 0,
            'coverage_percent': 0.0,
            'coverage_report': {},
            'errors': []
        }
        
        try:
            # Run pytest with coverage
            result = subprocess.run([
                'python', '-m', 'pytest', 'tests/', 
                '--cov=src', '--cov-report=json', '--cov-report=term',
                '-v'
            ], capture_output=True, text=True, cwd=self.project_root)
            
            # Parse pytest output
            if result.returncode == 0:
                test_results['tests_passed'] = len(re.findall(r'PASSED', result.stdout))
            else:
                test_results['tests_failed'] = len(re.findall(r'FAILED', result.stdout))
                test_results['errors'].append(f"Tests failed: {result.stderr}")
            
            test_results['tests_run'] = test_results['tests_passed'] + test_results['tests_failed']
            
            # Read coverage report
            coverage_file = self.project_root / 'coverage.json'
            if coverage_file.exists():
                with open(coverage_file, 'r') as f:
                    coverage_data = json.load(f)
                    test_results['coverage_percent'] = coverage_data.get('totals', {}).get('percent_covered', 0.0)
                    test_results['coverage_report'] = coverage_data.get('files', {})
            
        except Exception as e:
            test_results['errors'].append(f"Failed to run tests: {e}")
        
        return test_results
    
    def audit_project(self) -> ProjectAudit:
        """Run comprehensive audit of the entire project."""
        logger.info("Starting comprehensive project audit...")
        
        # Walk through all files
        for root, dirs, files in os.walk(self.project_root):
            # Skip directories we don't want to analyze
            dirs[:] = [d for d in dirs if d not in self.skip_dirs]
            
            for file in files:
                file_path = Path(root) / file
                
                if self.should_skip_path(file_path):
                    continue
                
                self.audit.total_files += 1
                analysis = self.analyze_file(file_path)
                
                # Categorize file
                file_type = analysis.file_type
                self.audit.files_by_type[file_type] = self.audit.files_by_type.get(file_type, 0) + 1
                
                if file_type == 'python':
                    self.audit.python_files.append(analysis)
                elif file_type in ['yaml', 'json', 'toml', 'config']:
                    self.audit.config_files.append(analysis)
                elif file_type == 'shell':
                    self.audit.script_files.append(analysis)
                elif file_type == 'markdown':
                    self.audit.doc_files.append(analysis)
                else:
                    self.audit.other_files.append(analysis)
                
                # Collect issues
                for issue in analysis.issues:
                    self.audit.issues_summary[issue] = self.audit.issues_summary.get(issue, 0) + 1
        
        # Run existing tests
        logger.info("Running existing test suite...")
        self.audit.test_coverage_summary = self.run_existing_tests()
        
        logger.info(f"Audit completed: {self.audit.total_files} files analyzed")
        return self.audit
    
    def generate_report(self) -> str:
        """Generate comprehensive audit report."""
        report = []
        report.append("# Comprehensive File Audit Report")
        report.append(f"Generated on: {__import__('datetime').datetime.now().isoformat()}")
        report.append("")
        
        # Summary
        report.append("## Summary")
        report.append(f"- **Total Files Analyzed**: {self.audit.total_files}")
        report.append(f"- **Python Files**: {len(self.audit.python_files)}")
        report.append(f"- **Configuration Files**: {len(self.audit.config_files)}")
        report.append(f"- **Shell Scripts**: {len(self.audit.script_files)}")
        report.append(f"- **Documentation Files**: {len(self.audit.doc_files)}")
        report.append(f"- **Other Files**: {len(self.audit.other_files)}")
        report.append("")
        
        # File types breakdown
        report.append("## File Types Breakdown")
        for file_type, count in sorted(self.audit.files_by_type.items()):
            report.append(f"- **{file_type.title()}**: {count} files")
        report.append("")
        
        # Test coverage summary
        report.append("## Test Coverage Summary")
        coverage = self.audit.test_coverage_summary
        report.append(f"- **Tests Run**: {coverage.get('tests_run', 0)}")
        report.append(f"- **Tests Passed**: {coverage.get('tests_passed', 0)}")
        report.append(f"- **Tests Failed**: {coverage.get('tests_failed', 0)}")
        report.append(f"- **Coverage Percentage**: {coverage.get('coverage_percent', 0):.1f}%")
        
        if coverage.get('errors'):
            report.append("- **Test Errors**:")
            for error in coverage['errors']:
                report.append(f"  - {error}")
        report.append("")
        
        # Python files analysis
        report.append("## Python Files Analysis")
        python_with_tests = sum(1 for f in self.audit.python_files if f.has_tests)
        report.append(f"- **Files with Tests**: {python_with_tests}/{len(self.audit.python_files)}")
        
        untested_files = [f for f in self.audit.python_files if not f.has_tests]
        if untested_files:
            report.append("- **Files Missing Tests**:")
            for file in untested_files:
                report.append(f"  - {file.path}")
        report.append("")
        
        # Security issues
        security_issues = []
        for file in self.audit.python_files + self.audit.config_files + self.audit.script_files:
            if file.security_issues:
                security_issues.extend([(file.path, issue) for issue in file.security_issues])
        
        if security_issues:
            report.append("## Security Issues")
            for file_path, issue in security_issues:
                report.append(f"- **{file_path}**: {issue}")
            report.append("")
        
        # Issues summary
        if self.audit.issues_summary:
            report.append("## Issues Summary")
            for issue, count in sorted(self.audit.issues_summary.items()):
                report.append(f"- **{issue}**: {count} files")
            report.append("")
        
        # Detailed file analysis
        report.append("## Detailed File Analysis")
        
        # Python files
        if self.audit.python_files:
            report.append("### Python Files")
            for file in sorted(self.audit.python_files, key=lambda x: x.path):
                report.append(f"#### {file.path}")
                report.append(f"- **Size**: {file.size} bytes, {file.lines} lines")
                report.append(f"- **Functions**: {len(file.functions)}")
                report.append(f"- **Classes**: {len(file.classes)}")
                report.append(f"- **Has Tests**: {'✅' if file.has_tests else '❌'}")
                report.append(f"- **Complexity Score**: {file.complexity_score}")
                
                if file.issues:
                    report.append("- **Issues**:")
                    for issue in file.issues:
                        report.append(f"  - {issue}")
                
                if file.security_issues:
                    report.append("- **Security Issues**:")
                    for issue in file.security_issues:
                        report.append(f"  - {issue}")
                report.append("")
        
        # Configuration files
        if self.audit.config_files:
            report.append("### Configuration Files")
            for file in sorted(self.audit.config_files, key=lambda x: x.path):
                report.append(f"#### {file.path}")
                report.append(f"- **Type**: {file.file_type}")
                report.append(f"- **Size**: {file.size} bytes, {file.lines} lines")
                
                if file.issues:
                    report.append("- **Issues**:")
                    for issue in file.issues:
                        report.append(f"  - {issue}")
                report.append("")
        
        # Shell scripts
        if self.audit.script_files:
            report.append("### Shell Scripts")
            for file in sorted(self.audit.script_files, key=lambda x: x.path):
                report.append(f"#### {file.path}")
                report.append(f"- **Size**: {file.size} bytes, {file.lines} lines")
                
                if file.issues:
                    report.append("- **Issues**:")
                    for issue in file.issues:
                        report.append(f"  - {issue}")
                
                if file.security_issues:
                    report.append("- **Security Issues**:")
                    for issue in file.security_issues:
                        report.append(f"  - {issue}")
                report.append("")
        
        return "\n".join(report)
    
    def save_report(self, filename: str = "comprehensive_audit_report.md"):
        """Save audit report to file."""
        report_content = self.generate_report()
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logger.info(f"Audit report saved to {filename}")
        
        # Also save JSON data
        json_filename = filename.replace('.md', '.json')
        audit_data = {
            'summary': {
                'total_files': self.audit.total_files,
                'files_by_type': self.audit.files_by_type,
                'test_coverage': self.audit.test_coverage_summary
            },
            'python_files': [
                {
                    'path': f.path,
                    'has_tests': f.has_tests,
                    'functions': len(f.functions),
                    'classes': len(f.classes),
                    'complexity': f.complexity_score,
                    'issues': f.issues,
                    'security_issues': f.security_issues
                }
                for f in self.audit.python_files
            ],
            'issues_summary': self.audit.issues_summary
        }
        
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(audit_data, f, indent=2)
        
        logger.info(f"Audit data saved to {json_filename}")

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Comprehensive file audit for Voice AI Agent")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    parser.add_argument("--output", default="comprehensive_audit_report.md", help="Output report filename")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run audit
    auditor = ComprehensiveFileAuditor(args.project_root)
    audit_results = auditor.audit_project()
    
    # Generate and save report
    auditor.save_report(args.output)
    
    # Print summary
    print(f"\n{'='*60}")
    print("COMPREHENSIVE AUDIT SUMMARY")
    print(f"{'='*60}")
    print(f"Total Files Analyzed: {audit_results.total_files}")
    print(f"Python Files: {len(audit_results.python_files)}")
    print(f"Files with Tests: {sum(1 for f in audit_results.python_files if f.has_tests)}")
    print(f"Test Coverage: {audit_results.test_coverage_summary.get('coverage_percent', 0):.1f}%")
    print(f"Total Issues Found: {sum(audit_results.issues_summary.values())}")
    print(f"Report saved to: {args.output}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()