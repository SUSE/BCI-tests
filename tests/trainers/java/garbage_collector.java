/**
Test garbage collector
This test reserve two byte arrays of 1Mb (step 1), 
then release one of these bytes (step 2).
The released memory in step 2 should be oneMb or more
than in step 1
*/
public class GarbageCollectorTest
{
  public static void main(String[] args)
  {
    Runtime rt = Runtime.getRuntime();
    int oneMb = 1048576;
    byte a[] = new byte[oneMb];
    byte b[] = new byte[oneMb];
    long freeMemory = rt.freeMemory();
    System.out.println( "free memory: " + rt.freeMemory() );
    a=null;
    System.gc();
    System.out.println( "free memory: " + rt.freeMemory() );
    assert freeMemory - oneMb >= rt.freeMemory();
  }
}