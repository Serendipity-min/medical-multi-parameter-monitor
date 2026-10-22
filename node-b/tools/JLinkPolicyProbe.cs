// 仅检查本地DLL策略命令的解析能力；没有Open/Connect/读目标/写目标入口。
using System;
using System.Runtime.InteropServices;
using System.Text;

class JLinkPolicyProbe {
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern IntPtr LoadLibraryEx(string name, IntPtr reserved, uint flags);
    [DllImport("kernel32.dll", CharSet=CharSet.Ansi, SetLastError=true)]
    static extern IntPtr GetProcAddress(IntPtr module, string name);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    delegate int Exec(string command, StringBuilder output, int capacity);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    delegate int Version();

    static int Main(string[] args) {
        if (args.Length != 1) return 2;
        // 进程位数由构建显式指定；仅载入明确路径DLL，不启动Commander或枚举探针。
        IntPtr library = LoadLibraryEx(args[0], IntPtr.Zero, 8);
        if (library == IntPtr.Zero) throw new Exception("DLL load failed: "+Marshal.GetLastWin32Error());
        Exec exec = (Exec)Marshal.GetDelegateForFunctionPointer(GetProcAddress(library,"JLINKARM_ExecCommand"),typeof(Exec));
        Version version = (Version)Marshal.GetDelegateForFunctionPointer(GetProcAddress(library,"JLINKARM_GetDLLVersion"),typeof(Version));
        Console.OutputEncoding = new UTF8Encoding(false);
        Console.WriteLine("DLL_VERSION="+version());
        foreach (string command in new string[]{"SetRestartOnClose = 0", "SetRestartOnClose 0", "DisableAutoUpdateFW = 1",
                  "InhibitConnectRetries = 1", "InhibitConnectRetries=1", "InhibitConnectRetries 1",
                  "ForceAttachTarget = 1", "ForceAttachTarget=1", "ForceAttachTarget 1",
                  "SetSkipDebugDeInit = 1", "SetDbgPowerDownOnClose = 0",
                  "MPM_UNKNOWN_POLICY_NEGATIVE = 1"}) {
            StringBuilder output = new StringBuilder(1024);
            int result = exec(command, output, output.Capacity);
            Console.WriteLine(command+"\t"+result+"\t"+output.ToString().Replace("\r"," ").Replace("\n"," "));
        }
        // 不调用Close：本程序从未Open，避免把设备生命周期操作带入脱机探针。
        return 0;
    }
}
