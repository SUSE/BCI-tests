using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;

namespace FipsTester;

public enum TestResult
{
    Pass,
    Error,
    Blocked
}

class TestRun
{
    public string Algo { get; set; }
    public TestResult Result { get; set; }
    public string? Hex { get; set; }
    public Exception? Error { get; set; }

    public TestRun(string algo, TestResult result, string hex)
    {
        Algo = algo;
        Result = result;
        Hex = hex;
        Error = null;
    }

    public TestRun(string algo, TestResult result, Exception ex)
    {
        bool isBlocked = false;

        if (ex is CryptographicException)
        {
            string[] blockedMsg = { "routines::unsupported", "routines::invalid modulus", "routines::initialization error" };
            isBlocked = blockedMsg.Any(msg => ex.Message.Contains(msg));
        }

        Algo = algo;
        Result = isBlocked ? TestResult.Blocked : result;
        Hex = null;
        Error = ex;
    }
}

class Program
{
    static void Main(string[] args)
    {
        Console.WriteLine("###############################");
        Console.WriteLine("# .NET FIPS Verification Test #");
        Console.WriteLine("###############################");

        bool isFipsEnabled = CheckFipsEnabled();

        if (!isFipsEnabled)
        {
            Console.WriteLine($"[WARN] FIPS mode is not enabled on the host!");
        }

        TestRun testAesCbc = TestAesCbc();
        TestRun testDES = TestDES();
        TestRun testTripleDES = TestTripleDES();
        TestRun testECDSAP256 = TestECDSAP256();
        TestRun testMD5 = TestMD5();
        TestRun testRC2 = TestRC2();
        TestRun testRSA1024 = TestRSA1024();
        TestRun testRSA2048 = TestRSA2048();
        TestRun testSHA256 = TestSHA256();
        TestRun testSHA512 = TestSHA512();

        var dubiousTests = new[] { testMD5 };
        var forbiddenTests = new[] { testDES, testTripleDES, testRC2, testRSA1024 };
        var approvedTests = new[] { testSHA256, testSHA512, testAesCbc, testRSA2048, testECDSAP256 };

        // Most algorithms should either be Pass or Blocked, but MD5 we don't
        // care as long as it does not errors out.
        // See: https://github.com/dotnet/runtime/commit/7bc40a5a0a29411981e64733b803f7a16fedbd86
        bool testPass = forbiddenTests.All(t => t.Result == TestResult.Blocked) &&
                        approvedTests.All(t => t.Result == TestResult.Pass) &&
                        dubiousTests.All(t => t.Result != TestResult.Error);

        PrintAlgo("### FORBIDDEN ALGORITHMS ###", forbiddenTests);
        PrintAlgo("### APPROVED ALGORITHMS ###", approvedTests);
        PrintAlgo("### DUBIOUS ALGORITHMS ###", dubiousTests);

        if (testMD5.Result == TestResult.Pass)
        {
            // MD5 explicitly disables FIPS enforcement
            // See: https://github.com/dotnet/runtime/commit/7bc40a5a0a29411981e64733b803f7a16fedbd86
            Console.WriteLine($"[WARN] MD5 passed because .NET uses a non-FIPS implementation!");
        }

        if (testPass)
        {
            Console.WriteLine("[PASS] FIPS mode is strictly enforced and functioning as expected.");
            Environment.Exit(0);
        }
        else
        {
            Console.WriteLine("[FAIL] FIPS enforcement test failed.");
            Environment.Exit(1);
        }
    }

    private static bool CheckFipsEnabled()
    {
        const string fipsPath = "/proc/sys/crypto/fips_enabled";
        try
        {
            if (File.Exists(fipsPath))
            {
                string content = File.ReadAllText(fipsPath).Trim();
                return content == "1";
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[ERROR] Unable to read {fipsPath}: {ex.Message}");
        }

        return false;
    }

    private static void PrintAlgo(string header, TestRun[] tests)
    {
        Console.WriteLine(header);

        foreach (var test in tests)
        {
            if (test.Result == TestResult.Error && test.Error != null)
            {
                Console.WriteLine($"{test.Algo.PadRight(12)}: {test.Result} ({test.Error.Message})");
            }
            else
            {
                Console.WriteLine($"{test.Algo.PadRight(12)}: {test.Result}");
            }
        }
    }

    private static TestRun TestSHA256()
    {
        try
        {
            byte[] input = Encoding.UTF8.GetBytes("Hello, FIPS!");
            using (SHA256 sha256 = SHA256.Create())
            {
                byte[] hash = sha256.ComputeHash(input);
                string hex = Convert.ToHexString(hash);
                return new TestRun("SHA-256", TestResult.Pass, hex);
            }
        }
        catch (Exception ex)
        {
            return new TestRun("SHA-256", TestResult.Error, ex);
        }
    }

    private static TestRun TestSHA512()
    {
        try
        {
            byte[] input = Encoding.UTF8.GetBytes("Hello, FIPS!");
            using (SHA512 sha512 = SHA512.Create())
            {
                byte[] hash = sha512.ComputeHash(input);
                string hex = Convert.ToHexString(hash);
                return new TestRun("SHA-512", TestResult.Pass, hex);
            }
        }
        catch (Exception ex)
        {
            return new TestRun("SHA-512", TestResult.Error, ex);
        }
    }

    private static TestRun TestMD5()
    {
        try
        {
            byte[] input = Encoding.UTF8.GetBytes("Hello, FIPS!");
            using (MD5 md5 = MD5.Create())
            {
                byte[] hash = md5.ComputeHash(input);
                string hex = Convert.ToHexString(hash);
                return new TestRun("MD5", TestResult.Pass, hex);
            }
        }
        catch (Exception ex)
        {
            return new TestRun("MD5", TestResult.Error, ex);
        }
    }

    private static TestRun TestDES()
    {
        try
        {
            byte[] input = Encoding.UTF8.GetBytes("Hello, FIPS!");
            using (DES des = DES.Create())
            {
                des.GenerateKey();
                des.GenerateIV();
                using (ICryptoTransform encryptor = des.CreateEncryptor())
                {
                    byte[] cipherText = encryptor.TransformFinalBlock(input, 0, input.Length);
                    string hex = Convert.ToHexString(cipherText);
                    return new TestRun("DES", TestResult.Pass, hex);
                }
            }
        }
        catch (Exception ex)
        {
            return new TestRun("DES", TestResult.Error, ex);
        }
    }

    private static TestRun TestTripleDES()
    {
        try
        {
            byte[] input = Encoding.UTF8.GetBytes("Hello, FIPS!");
            using (TripleDES tripleDes = TripleDES.Create())
            {
                tripleDes.GenerateKey();
                tripleDes.GenerateIV();
                using (ICryptoTransform encryptor = tripleDes.CreateEncryptor())
                {
                    byte[] cipherText = encryptor.TransformFinalBlock(input, 0, input.Length);
                    string hex = Convert.ToHexString(cipherText);
                    return new TestRun("3DES", TestResult.Pass, hex);
                }
            }
        }
        catch (Exception ex)
        {
            return new TestRun("3DES", TestResult.Error, ex);
        }
    }

    private static TestRun TestRC2()
    {
        try
        {
            byte[] input = Encoding.UTF8.GetBytes("Hello, FIPS!");
            using (RC2 rc2 = RC2.Create())
            {
                rc2.GenerateKey();
                rc2.GenerateIV();
                using (ICryptoTransform encryptor = rc2.CreateEncryptor())
                {
                    byte[] cipherText = encryptor.TransformFinalBlock(input, 0, input.Length);
                    string hex = Convert.ToHexString(cipherText);
                    return new TestRun("RC2", TestResult.Pass, hex);
                }
            }
        }
        catch (Exception ex)
        {
            return new TestRun("RC2", TestResult.Error, ex);
        }
    }

    private static TestRun TestRSA1024()
    {
        try
        {
            using (RSA rsa = RSA.Create(1024))
            {
                byte[] input = Encoding.UTF8.GetBytes("Hello, FIPS!");
                byte[] signature = rsa.SignData(input, HashAlgorithmName.SHA256, RSASignaturePadding.Pkcs1);
                string hex = Convert.ToHexString(signature);
                return new TestRun("RSA1024", TestResult.Pass, hex);
            }
        }
        catch (Exception ex)
        {
            return new TestRun("RSA-1024", TestResult.Error, ex);
        }
    }

    private static TestRun TestRSA2048()
    {
        try
        {
            using (RSA rsa = RSA.Create(2048))
            {
                byte[] input = Encoding.UTF8.GetBytes("Hello, FIPS!");
                byte[] signature = rsa.SignData(input, HashAlgorithmName.SHA256, RSASignaturePadding.Pkcs1);
                string hex = Convert.ToHexString(signature);
                return new TestRun("RSA2048", TestResult.Pass, hex);
            }
        }
        catch (Exception ex)
        {
            return new TestRun("RSA-2048", TestResult.Error, ex);
        }
    }

    private static TestRun TestAesCbc()
    {
        try
        {
            byte[] input = Encoding.UTF8.GetBytes("Hello, FIPS!");
            using (Aes aes = Aes.Create())
            {
                aes.KeySize = 256;
                aes.Mode = CipherMode.CBC;
                aes.Padding = PaddingMode.PKCS7;
                aes.GenerateKey();
                aes.GenerateIV();

                using (ICryptoTransform encryptor = aes.CreateEncryptor())
                {
                    byte[] cipherText = encryptor.TransformFinalBlock(input, 0, input.Length);
                    string hex = Convert.ToHexString(cipherText);
                    return new TestRun("AES-CBC", TestResult.Pass, hex);
                }
            }
        }
        catch (Exception ex)
        {
            return new TestRun("AES-CBC", TestResult.Error, ex);
        }
    }

    private static TestRun TestECDSAP256()
    {
        try
        {
            using (ECDsa ecdsa = ECDsa.Create(ECCurve.NamedCurves.nistP256))
            {
                byte[] input = Encoding.UTF8.GetBytes("Hello, FIPS!");
                byte[] signature = ecdsa.SignData(input, HashAlgorithmName.SHA256);
                string hex = Convert.ToHexString(signature);
                return new TestRun("ECDSA P-256", TestResult.Pass, hex);
            }
        }
        catch (Exception ex)
        {
            return new TestRun("ECDSA P-256", TestResult.Error, ex);
        }
    }
}
