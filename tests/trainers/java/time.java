/**
Test to check the Java Timming. This covers operations
that are related with the interaction of java with the
system where is running.
- Date
- LocalTimeDate
- currentTimeMillis
- nanoTime
- instant
*/
import java.util.*;
import java.time.*;

public class Test {
    static void date() throws Exception {
        Date d1 = new Date();
        Thread.sleep(100);
        Date d2 = new Date();
        assert d2.getTime() <= (d1.getTime() + 100);
    }

    static void localTimeDate() throws Exception {
        LocalDateTime now = LocalDateTime.now();
        assert now.getYear() > 2020 && now.getYear() < 2100;
    }

    static void currentTimeMillis() throws Exception {
        long t1 = System.currentTimeMillis();
        Thread.sleep(100);
        long t2 = System.currentTimeMillis();
        assert t2 <= (t1 + 100);
    }

    static void nanoTime() throws Exception {
        long t1 = System.nanoTime();
        Thread.sleep(100);
        long t2 = System.nanoTime();
        assert t2 <= (t1 + 1000000);
    }

    static void instant() throws Exception {
        Instant t1 = Instant.now();
        Thread.sleep(100);
        Instant t2 = Instant.now();
        assert Duration.between(t1, t2).toMillis() <= 100;
    }

    public static void main(String[] args) {
        try {
            Test.date();
            Test.localTimeDate();
            Test.currentTimeMillis();
            Test.nanoTime();
            Test.instant();
            System.out.println("All OK");
        } catch (Exception e) {
            e.printStackTrace();
            System.exit(1);
        }
    }
}
