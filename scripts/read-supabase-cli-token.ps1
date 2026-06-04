#Requires -Version 5.1
<#
.SYNOPSIS
  Read Supabase CLI access token from Windows Credential Manager (if supabase login was used).
  Does not print the token; returns it on stdout for piping to gh secret set.
#>
$ErrorActionPreference = "Stop"

Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public class SupabaseCredMan {
  [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
  public struct CREDENTIAL {
    public uint Flags;
    public uint Type;
    public IntPtr TargetName;
    public IntPtr Comment;
    public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
    public uint CredentialBlobSize;
    public IntPtr CredentialBlob;
    public uint Persist;
    public uint AttributeCount;
    public IntPtr Attributes;
    public IntPtr TargetAlias;
    public IntPtr UserName;
  }
  [DllImport("advapi32", SetLastError=true, CharSet=CharSet.Unicode)]
  public static extern bool CredRead(string target, uint type, uint reservedFlag, out IntPtr credential);
  [DllImport("advapi32")] public static extern bool CredFree(IntPtr cred);
}
"@

$targets = @("Supabase CLI:supabase", "LegacyGeneric:target=Supabase CLI:supabase")
foreach ($target in $targets) {
    $ptr = [IntPtr]::Zero
    if (-not [SupabaseCredMan]::CredRead($target, 1, 0, [ref]$ptr)) { continue }
    try {
        $cred = [Runtime.InteropServices.Marshal]::PtrToStructure($ptr, [type][SupabaseCredMan+CREDENTIAL])
        $size = [int]$cred.CredentialBlobSize
        if ($size -le 0) { continue }
        $blob = New-Object byte[] $size
        [Runtime.InteropServices.Marshal]::Copy($cred.CredentialBlob, $blob, 0, $size)
        $token = [Text.Encoding]::UTF8.GetString($blob).Trim()
        if ($token) { return $token }
    } finally {
        [void][SupabaseCredMan]::CredFree($ptr)
    }
}

return $null
