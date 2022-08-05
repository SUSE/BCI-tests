/**
Test subprocesses
Executes a subprocess and check the exit value
and the results
*/
import java.io.*;
import java.util.Scanner;

public class SubprocessesTest
{
  public static void main(String[] args)
  {
    try {
        Process process = Runtime.getRuntime().exec(new String[] { "ls", "/" });
        process.waitFor();

        assert process.exitValue() == 0;

        Scanner scanner = new Scanner(process.getInputStream());
        while (scanner.hasNextLine()) {
            System.out.println(scanner.nextLine());
        }
        scanner.close();
    } catch(Exception ex) {
        System.exit(1);
    }
  }
}
