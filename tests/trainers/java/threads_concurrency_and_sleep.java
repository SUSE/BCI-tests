/**
Test to check the Java Threading module.
It runs two concurrent tests and waits for them to end.
The `BasicThread2` child class additionally includes a 
passive wait (sleep) for 1 second.
*/
public class Test {
    public static void main(String[] args) {
        BasicThread t1 = new BasicThread("1");
        t1.start();
        BasicThread2 t2 = new BasicThread2("2");
        t2.start();

        try {
          t1.join();
          t2.join();
        } catch ( InterruptedException e) {
          System.out.println("Interrupted");
        }
    }
}

class BasicThread extends Thread {
  protected String tid;

  BasicThread(String id) {
    tid = id;
  }

  public void run() {
    printIam();
  }

  protected void printIam(){
    System.out.println("I am the thread ".concat(tid));
  }
}

class BasicThread2 extends BasicThread {
  BasicThread2(String id) {
    super(id);
  }

  public void run() {
    try{
      Thread.sleep(1000);
    }catch(InterruptedException err){
      System.out.print("Error in sleep");  
    }
    printIam();
  }
}
