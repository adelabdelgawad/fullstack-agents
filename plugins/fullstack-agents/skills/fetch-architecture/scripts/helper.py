#!/usr/bin/env python3
"""
Fetch Architecture Helper Script

Utilities for managing Next.js fetch utilities.

Usage:
    python helper.py validate        # Validate fetch configuration
    python helper.py routes          # List API routes
    python helper.py generate NAME   # Generate API route for entity
    python helper.py actions NAME    # Generate server actions for entity
"""

import sys
import os
import re


def validate_fetch_config():
    """Validate fetch architecture configuration and scan for violations."""
    print("Validating fetch architecture...")

    issues = []
    passed = 0

    # Check required files exist
    required_files = [
        'lib/fetch/client.ts',
        'lib/fetch/server.ts',
        'lib/fetch/backend.ts',
        'lib/fetch/api-route-helper.ts',
        'lib/fetch/errors.ts',
        'lib/fetch/types.ts',
    ]

    for file in required_files:
        if os.path.exists(file):
            print(f"  [PASS] {file}")
            passed += 1
            with open(file, 'r') as f:
                content = f.read()
                if file.endswith('server.ts'):
                    if '"use server"' not in content:
                        issues.append(f"  [FAIL] {file}: Missing 'use server' directive")
                    # server.ts SHOULD call backend directly (new architecture)
                    if 'directBackendFetch' not in content and 'getAccessToken' not in content:
                        issues.append(f"  [FAIL] {file}: Missing directBackendFetch — server.ts must call backend directly")
                    else:
                        passed += 1
                    if 'getServerCsrfToken' not in content:
                        issues.append(f"  [WARN] {file}: Missing getServerCsrfToken — mutations need CSRF")
                    else:
                        passed += 1
                if file.endswith('client.ts'):
                    if '"use client"' not in content:
                        issues.append(f"  [FAIL] {file}: Missing 'use client' directive")
                    if 'csrfManager' not in content:
                        issues.append(f"  [WARN] {file}: Missing csrfManager — mutations need CSRF")
                    else:
                        passed += 1
                    if 'export const api' not in content:
                        issues.append(f"  [FAIL] {file}: Missing 'api' export — should export api object, not fetchClient")
                    else:
                        passed += 1
                if file.endswith('backend.ts'):
                    if 'backendFetch' not in content:
                        issues.append(f"  [FAIL] {file}: Missing backendFetch function")
                    else:
                        passed += 1
                if file.endswith('api-route-helper.ts'):
                    if 'withAuth' not in content:
                        issues.append(f"  [FAIL] {file}: Missing withAuth wrapper")
                    else:
                        passed += 1
                    if 'forwardHeaders' not in content:
                        issues.append(f"  [FAIL] {file}: Missing forwardHeaders — mutations need CSRF forwarding")
                    else:
                        passed += 1
                    if 'isTokenExpired' not in content:
                        issues.append(f"  [WARN] {file}: Missing isTokenExpired — pre-emptive refresh recommended")
                    else:
                        passed += 1
        else:
            issues.append(f"  [FAIL] {file}: Not found")

    # Check 1: Server actions must use /backend/ URLs, not /api/
    actions_dir = 'lib/actions'
    if os.path.isdir(actions_dir):
        print(f"\n--- Server Actions ({actions_dir}/) ---")

        action_issues = False
        for root, _, files in os.walk(actions_dir):
            for filename in files:
                if not filename.endswith('.ts'):
                    continue
                filepath = os.path.join(root, filename)
                with open(filepath, 'r') as f:
                    lines = f.readlines()
                for lineno, line in enumerate(lines, 1):
                    stripped = line.strip()
                    if stripped.startswith('//'):
                        continue
                    # Server actions should NOT use /api/ prefix
                    if re.search(r"serverGet|serverPost|serverPut|serverDelete", line):
                        if "'/api/" in line or '"/api/' in line or '`/api/' in line:
                            issues.append(
                                f"  [FAIL] {filepath}:{lineno}: Uses /api/ URL — should use /backend/ prefix"
                            )
                            action_issues = True
                    # Server actions should NOT import backendFetch
                    if 'backendFetch' in line and 'import' in line:
                        issues.append(
                            f"  [FAIL] {filepath}:{lineno}: Imports backendFetch — only allowed in app/api/"
                        )
                        action_issues = True
                    # Server actions should NOT import from api-route-helper
                    if 'api-route-helper' in line and 'import' in line:
                        issues.append(
                            f"  [FAIL] {filepath}:{lineno}: Imports from api-route-helper — only allowed in app/api/"
                        )
                        action_issues = True

        if not action_issues:
            print("  [PASS] All server actions use /backend/ URLs")
            print("  [PASS] No backendFetch imports in server actions")
            passed += 2

    # Check 2: API routes must import from backend.ts, not server.ts
    api_dir = 'app/api'
    if os.path.isdir(api_dir):
        print(f"\n--- API Routes ({api_dir}/) ---")

        route_issues = False
        for root, _, files in os.walk(api_dir):
            for filename in files:
                if not filename.endswith('.ts') and not filename.endswith('.tsx'):
                    continue
                filepath = os.path.join(root, filename)
                with open(filepath, 'r') as f:
                    content = f.read()
                    lines = content.split('\n')

                for lineno, line in enumerate(lines, 1):
                    # Should NOT import backendFetch from server.ts
                    if 'backendFetch' in line and 'server' in line and 'import' in line:
                        issues.append(
                            f"  [FAIL] {filepath}:{lineno}: Imports backendFetch from server — use @/lib/fetch/backend"
                        )
                        route_issues = True
                    # Should NOT use backendGet/Post/Put/Delete helpers
                    if re.search(r'\bbackendGet\b|\bbackendPost\b|\bbackendPut\b|\bbackendDelete\b', line):
                        if 'import' in line or not line.strip().startswith('//'):
                            issues.append(
                                f"  [FAIL] {filepath}:{lineno}: Uses backendGet/Post/Put/Delete helper — call backendFetch() directly"
                            )
                            route_issues = True

                # Check mutation handlers use (token, headers)
                for method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                    if f'function {method}' in content:
                        # Find the withAuth call near this method
                        method_match = re.search(
                            rf'function {method}.*?withAuth\((.*?)\)',
                            content,
                            re.DOTALL
                        )
                        if method_match:
                            callback = method_match.group(1).strip()
                            if 'headers' not in callback and 'token' in callback:
                                # Find line number
                                pos = method_match.start()
                                ln = content[:pos].count('\n') + 1
                                issues.append(
                                    f"  [WARN] {filepath}:{ln}: {method} handler uses (token) — mutations should use (token, headers) for CSRF"
                                )
                                route_issues = True

        if not route_issues:
            print("  [PASS] All API routes import from @/lib/fetch/backend")
            print("  [PASS] No backendGet/Post/Put/Delete helpers")
            print("  [PASS] Mutation handlers use (token, headers) pattern")
            passed += 3

    # Check 3: Client components must use api, not fetchClient
    print(f"\n--- Client Components ---")
    client_issues = False
    for search_dir in ['app', 'components']:
        if not os.path.isdir(search_dir):
            continue
        for root, _, files in os.walk(search_dir):
            for filename in files:
                if not filename.endswith('.tsx') and not filename.endswith('.ts'):
                    continue
                filepath = os.path.join(root, filename)
                with open(filepath, 'r') as f:
                    lines = f.readlines()
                for lineno, line in enumerate(lines, 1):
                    if line.strip().startswith('//'):
                        continue
                    if 'fetchClient' in line:
                        issues.append(
                            f"  [FAIL] {filepath}:{lineno}: Uses fetchClient — replace with api"
                        )
                        client_issues = True

    if not client_issues:
        print("  [PASS] No fetchClient usage in components")
        passed += 1

    # Check 4: No SWR (unless justified)
    print(f"\n--- Data Strategy ---")
    swr_found = False
    for search_dir in ['app', 'components', 'lib']:
        if not os.path.isdir(search_dir):
            continue
        for root, _, files in os.walk(search_dir):
            for filename in files:
                if not filename.endswith('.tsx') and not filename.endswith('.ts'):
                    continue
                filepath = os.path.join(root, filename)
                with open(filepath, 'r') as f:
                    content = f.read()
                if 'from "swr"' in content or "from 'swr'" in content or 'useSWR' in content:
                    issues.append(f"  [WARN] {filepath}: Contains SWR import — Strategy A only unless justified")
                    swr_found = True

    if not swr_found:
        print("  [PASS] No SWR imports (Strategy A)")
        passed += 1

    # Summary
    print(f"\n{'=' * 60}")
    print(f"RESULTS: {passed} passed, {len(issues)} issues")
    print(f"{'=' * 60}")

    if issues:
        print("\nIssues:")
        for issue in issues:
            print(issue)
        return False
    else:
        print("\nAll fetch architecture checks passed!")
        return True


def list_api_routes():
    """List all API routes in the application."""
    print("Scanning API routes...")

    api_dir = 'app/api'
    if not os.path.isdir(api_dir):
        print(f"  [FAIL] {api_dir} directory not found")
        return

    routes = []

    for root, dirs, files in os.walk(api_dir):
        if 'route.ts' in files or 'route.tsx' in files:
            route_path = root.replace(api_dir, '/api')
            route_path = re.sub(r'\[(\w+)\]', r':\1', route_path)

            route_file = os.path.join(root, 'route.ts')
            if not os.path.exists(route_file):
                route_file = os.path.join(root, 'route.tsx')

            with open(route_file, 'r') as f:
                content = f.read()
                methods = []
                for method in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']:
                    if f'export async function {method}' in content or f'export function {method}' in content:
                        methods.append(method)

            routes.append({
                'path': route_path,
                'methods': methods,
                'file': route_file
            })

    if not routes:
        print("No API routes found")
        return

    print(f"\nFound {len(routes)} routes:\n")
    print(f"{'Path':<50} {'Methods':<30}")
    print("-" * 80)

    for route in sorted(routes, key=lambda r: r['path']):
        methods_str = ', '.join(route['methods'])
        print(f"{route['path']:<50} {methods_str:<30}")


def generate_api_route(entity_name: str, section: str = 'setting'):
    """Generate API route files for an entity."""
    print(f"Generating API route for: {entity_name} (section: {section})")

    path_name = entity_name.lower().replace('_', '-')
    entity_id = f"{entity_name.lower()}Id"

    base_dir = f"app/api/{section}/{path_name}"
    dynamic_dir = f"{base_dir}/[{entity_id}]"
    status_dir = f"{dynamic_dir}/status"
    bulk_status_dir = f"{base_dir}/status"

    os.makedirs(base_dir, exist_ok=True)
    os.makedirs(dynamic_dir, exist_ok=True)
    os.makedirs(status_dir, exist_ok=True)
    os.makedirs(bulk_status_dir, exist_ok=True)

    base_route = f'''import {{ withAuth }} from '@/lib/fetch/api-route-helper';
import {{ backendFetch }} from '@/lib/fetch/backend';

export async function GET(request: Request) {{
  const params = new URL(request.url).searchParams.toString();
  return withAuth((token) =>
    backendFetch(`/{section}/{path_name}?${{params}}`, token)
  );
}}

export async function POST(request: Request) {{
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch('/{section}/{path_name}', token, {{ method: 'POST', body, headers }})
  );
}}
'''

    dynamic_route = f'''import {{ withAuth }} from '@/lib/fetch/api-route-helper';
import {{ backendFetch }} from '@/lib/fetch/backend';

interface RouteParams {{
  params: Promise<{{ {entity_id}: string }}>;
}}

export async function GET(request: Request, {{ params }}: RouteParams) {{
  const {{ {entity_id} }} = await params;
  return withAuth((token) =>
    backendFetch(`/{section}/{path_name}/${{{entity_id}}}`, token)
  );
}}

export async function PUT(request: Request, {{ params }}: RouteParams) {{
  const {{ {entity_id} }} = await params;
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch(`/{section}/{path_name}/${{{entity_id}}}`, token, {{ method: 'PUT', body, headers }})
  );
}}

export async function DELETE(request: Request, {{ params }}: RouteParams) {{
  const {{ {entity_id} }} = await params;
  return withAuth((token, headers) =>
    backendFetch(`/{section}/{path_name}/${{{entity_id}}}`, token, {{ method: 'DELETE', headers }})
  );
}}
'''

    status_route = f'''import {{ withAuth }} from '@/lib/fetch/api-route-helper';
import {{ backendFetch }} from '@/lib/fetch/backend';

interface RouteParams {{
  params: Promise<{{ {entity_id}: string }}>;
}}

export async function PUT(request: Request, {{ params }}: RouteParams) {{
  const {{ {entity_id} }} = await params;
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch(`/{section}/{path_name}/${{{entity_id}}}/status`, token, {{ method: 'PUT', body, headers }})
  );
}}
'''

    bulk_status_route = f'''import {{ withAuth }} from '@/lib/fetch/api-route-helper';
import {{ backendFetch }} from '@/lib/fetch/backend';

export async function PUT(request: Request) {{
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch('/{section}/{path_name}/status', token, {{ method: 'PUT', body, headers }})
  );
}}
'''

    files = [
        (f"{base_dir}/route.ts", base_route),
        (f"{dynamic_dir}/route.ts", dynamic_route),
        (f"{status_dir}/route.ts", status_route),
        (f"{bulk_status_dir}/route.ts", bulk_status_route),
    ]

    for filepath, content in files:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"  Created {filepath}")


def generate_server_actions(entity_name: str, section: str = 'setting'):
    """Generate server actions for an entity."""
    print(f"Generating server actions for: {entity_name} (section: {section})")

    path_name = entity_name.lower().replace('_', '-')
    entity_pascal = ''.join(word.capitalize() for word in entity_name.split('_'))

    actions_dir = f'lib/actions/{section}' if section != 'setting' else 'lib/actions'
    os.makedirs(actions_dir, exist_ok=True)

    template = f'''"use server";

import {{ serverGet, serverPost, serverPut, serverDelete }} from "@/lib/fetch/server";
import type {{ {entity_pascal}, {entity_pascal}Create, {entity_pascal}Response }} from "@/lib/types/api/{path_name}";

export async function get{entity_pascal}s(
  limit: number = 10,
  skip: number = 0,
  filters?: Record<string, string | undefined>
): Promise<{entity_pascal}Response> {{
  const params = new URLSearchParams();
  params.append('limit', limit.toString());
  params.append('skip', skip.toString());

  if (filters) {{
    Object.entries(filters).forEach(([key, value]) => {{
      if (value) params.append(key, value);
    }});
  }}

  return serverGet<{entity_pascal}Response>(`/backend/{section}/{path_name}?${{params.toString()}}`);
}}

export async function get{entity_pascal}(id: string): Promise<{entity_pascal}> {{
  return serverGet<{entity_pascal}>(`/backend/{section}/{path_name}/${{id}}`);
}}

export async function create{entity_pascal}(
  data: {entity_pascal}Create
): Promise<{entity_pascal}> {{
  return serverPost<{entity_pascal}>("/backend/{section}/{path_name}", data);
}}

export async function update{entity_pascal}(
  id: string,
  data: Partial<{entity_pascal}>
): Promise<{entity_pascal}> {{
  return serverPut<{entity_pascal}>(`/backend/{section}/{path_name}/${{id}}`, data);
}}

export async function delete{entity_pascal}(id: string): Promise<void> {{
  return serverDelete(`/backend/{section}/{path_name}/${{id}}`);
}}
'''

    filepath = f"{actions_dir}/{path_name}.actions.ts"
    with open(filepath, 'w') as f:
        f.write(template)

    print(f"  Created {filepath}")
    print(f"\n  Don't forget to create types in lib/types/api/{path_name}.ts")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == 'validate':
        success = validate_fetch_config()
        sys.exit(0 if success else 1)
    elif command == 'routes':
        list_api_routes()
    elif command == 'generate' and len(sys.argv) > 2:
        section = sys.argv[3] if len(sys.argv) > 3 else 'setting'
        generate_api_route(sys.argv[2], section)
    elif command == 'actions' and len(sys.argv) > 2:
        section = sys.argv[3] if len(sys.argv) > 3 else 'setting'
        generate_server_actions(sys.argv[2], section)
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
