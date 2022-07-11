/**
Test memory limits
This test allocates memory in iterations of 1Mb
until when there are not enough memory failing
with an OutOfMemoryError execption
*/
import java.util.Vector;

public class MemoryTest
{
  public static void main(String[] args)
  {
    int iter = 0;
    Vector v = new Vector();
    while (true)
    {
      byte b[] = new byte[1048576];
      v.add(b);
      System.out.println("Iteration: (" + iter + ")");
      iter++;
    }
  }
}