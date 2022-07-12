/**
Test to check the Java System module 
environment variables
*/

public class Test {
    public static void main(String[] args) {
        try {
            assert System.getenv("ENV1") != null;
            System.out.println(System.getenv("ENV1"));
        } catch (Exception e) {
            e.printStackTrace();
            System.exit(1);
        }
    }
}
